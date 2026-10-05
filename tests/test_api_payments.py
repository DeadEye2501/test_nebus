"""Проверки HTTP API платежей: создание, чтение, идемпотентность, ключ доступа и валидация."""

import json
import uuid

import pytest

KEY = {"X-API-Key": "test-key"}
BODY = {
    "amount": "100.50",
    "currency": "RUB",
    "description": "Заказ 42",
    "metadata": {"order_id": 42},
    "webhook_url": "https://example.com/hook",
}


def _headers(idempotency_key: str = "key-1") -> dict[str, str]:
    return KEY | {"Idempotency-Key": idempotency_key}


async def test_create_returns_202_with_pending_payment(client):
    response = await client.post("/api/v1/payments", json=BODY, headers=_headers())

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    assert uuid.UUID(body["payment_id"])
    assert body["created_at"]


async def test_repeat_with_same_key_returns_same_payment(client):
    first = await client.post("/api/v1/payments", json=BODY, headers=_headers())
    second = await client.post("/api/v1/payments", json=BODY, headers=_headers())

    assert second.status_code == 202
    assert second.json()["payment_id"] == first.json()["payment_id"]


async def test_same_key_with_other_body_is_409(client):
    await client.post("/api/v1/payments", json=BODY, headers=_headers())

    response = await client.post(
        "/api/v1/payments", json=BODY | {"amount": "1.00"}, headers=_headers()
    )

    assert response.status_code == 409


async def test_get_returns_full_payment(client):
    created = await client.post("/api/v1/payments", json=BODY, headers=_headers())
    payment_id = created.json()["payment_id"]

    response = await client.get(f"/api/v1/payments/{payment_id}", headers=KEY)

    assert response.status_code == 200
    body = response.json()
    assert body["payment_id"] == payment_id
    assert body["amount"] == "100.50"
    assert body["metadata"] == {"order_id": 42}
    assert body["idempotency_key"] == "key-1"
    assert body["processed_at"] is None


async def test_unknown_payment_is_404(client):
    response = await client.get(f"/api/v1/payments/{uuid.uuid4()}", headers=KEY)

    assert response.status_code == 404


async def test_malformed_payment_id_is_422(client):
    response = await client.get("/api/v1/payments/not-a-uuid", headers=KEY)

    assert response.status_code == 422


@pytest.mark.parametrize("headers", [{}, {"X-API-Key": "wrong"}])
async def test_requests_without_valid_key_are_401(client, headers):
    created = await client.post(
        "/api/v1/payments", json=BODY, headers=headers | {"Idempotency-Key": "k"}
    )
    read = await client.get(f"/api/v1/payments/{uuid.uuid4()}", headers=headers)

    assert created.status_code == 401
    assert read.status_code == 401


async def test_missing_idempotency_key_is_422(client):
    response = await client.post("/api/v1/payments", json=BODY, headers=KEY)

    assert response.status_code == 422


@pytest.mark.parametrize("idempotency_key", ["", "k" * 256])
async def test_idempotency_key_out_of_bounds_is_422(client, idempotency_key):
    response = await client.post(
        "/api/v1/payments", json=BODY, headers=_headers(idempotency_key)
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "override",
    [
        {"amount": "0"},
        {"amount": "-1.00"},
        {"amount": "1.001"},
        {"amount": "12345678901234567.00"},
        {"currency": "GBP"},
        {"description": ""},
        {"metadata": [1, 2]},
        {"webhook_url": "ftp://example.com/hook"},
        {"webhook_url": "not a url"},
    ],
)
async def test_invalid_body_is_422_and_nothing_is_stored(client, override):
    response = await client.post("/api/v1/payments", json=BODY | override, headers=_headers())
    retry = await client.post("/api/v1/payments", json=BODY, headers=_headers())

    assert response.status_code == 422
    assert retry.status_code == 202


@pytest.mark.parametrize(
    "override",
    [
        {"description": "a\u0000b"},
        {"metadata": {"note": "a\u0000b"}},
        {"metadata": {"a\u0000b": 1}},
        {"metadata": {"nested": {"x": [1, float("nan")]}}},
        {"metadata": {"x": float("inf")}},
        {"metadata": {"x": float("-inf")}},
    ],
)
async def test_values_postgres_rejects_are_422_and_nothing_is_stored(client, override):
    raw = json.dumps(BODY | override, allow_nan=True).encode()

    response = await client.post(
        "/api/v1/payments",
        content=raw,
        headers=_headers() | {"Content-Type": "application/json"},
    )
    retry = await client.post("/api/v1/payments", json=BODY, headers=_headers())

    assert response.status_code == 422
    assert retry.status_code == 202
