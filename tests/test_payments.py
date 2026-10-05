"""Тесты создания платежа с идемпотентностью и outbox и чтения платежа."""

import asyncio
import uuid

import pytest
from sqlalchemy import func, select

from app import payments
from app.models import Currency, OutboxEvent, Payment, PaymentStatus
from app.payments import IdempotencyConflict, create_payment, get_payment
from tests.helpers import payment_body


async def _count(session_factory, model) -> int:
    async with session_factory() as session:
        return await session.scalar(select(func.count()).select_from(model))


async def test_create_stores_pending_payment_and_one_outbox_event(session_factory):
    payment = await create_payment(session_factory, "key-1", payment_body())

    assert payment.status is PaymentStatus.PENDING
    async with session_factory() as session:
        events = (await session.scalars(select(OutboxEvent))).all()
    assert [event.payload for event in events] == [{"payment_id": str(payment.id)}]


async def test_repeat_with_same_key_and_body_returns_same_payment_without_new_event(
    session_factory,
):
    first = await create_payment(session_factory, "key-1", payment_body())
    second = await create_payment(session_factory, "key-1", payment_body())

    assert second.id == first.id
    assert await _count(session_factory, Payment) == 1
    assert await _count(session_factory, OutboxEvent) == 1


async def test_same_body_written_differently_is_the_same_request(session_factory):
    first = await create_payment(
        session_factory, "key-1", payment_body(amount="100.50", metadata={"a": 1, "b": 2})
    )
    second = await create_payment(
        session_factory, "key-1", payment_body(amount="100.5", metadata={"b": 2, "a": 1})
    )

    assert second.id == first.id


async def test_same_key_with_different_body_is_a_conflict(session_factory):
    await create_payment(session_factory, "key-1", payment_body(amount="100.50"))

    with pytest.raises(IdempotencyConflict):
        await create_payment(session_factory, "key-1", payment_body(amount="200.00"))


async def test_concurrent_requests_with_same_key_create_one_payment(session_factory):
    first, second = await asyncio.gather(
        create_payment(session_factory, "key-1", payment_body()),
        create_payment(session_factory, "key-1", payment_body()),
    )

    assert first.id == second.id
    assert await _count(session_factory, Payment) == 1
    assert await _count(session_factory, OutboxEvent) == 1


def _miss_first_lookup(monkeypatch):
    """Первый поиск по ключу не видит платёж — как при гонке двух запросов."""
    real = payments._find_by_key
    calls = []

    async def find(session_factory, key):
        calls.append(key)
        return None if len(calls) == 1 else await real(session_factory, key)

    monkeypatch.setattr(payments, "_find_by_key", find)


async def test_lost_insert_race_with_same_body_returns_existing_payment(
    session_factory, monkeypatch
):
    first = await create_payment(session_factory, "key-1", payment_body())
    _miss_first_lookup(monkeypatch)

    second = await create_payment(session_factory, "key-1", payment_body())

    assert second.id == first.id
    assert await _count(session_factory, Payment) == 1
    assert await _count(session_factory, OutboxEvent) == 1


async def test_lost_insert_race_with_different_body_is_a_conflict(session_factory, monkeypatch):
    await create_payment(session_factory, "key-1", payment_body(amount="100.50"))
    _miss_first_lookup(monkeypatch)

    with pytest.raises(IdempotencyConflict):
        await create_payment(session_factory, "key-1", payment_body(amount="200.00"))


async def test_get_returns_stored_payment_or_none(session_factory):
    created = await create_payment(session_factory, "key-1", payment_body())

    found = await get_payment(session_factory, created.id)

    assert found.meta == {"order_id": 42, "source": "web"}
    assert str(found.amount) == "100.50"
    assert found.currency is Currency.RUB
    assert found.description == "Заказ 42"
    assert found.webhook_url == "https://example.com/hook"
    assert found.idempotency_key == "key-1"
    assert await get_payment(session_factory, uuid.uuid4()) is None
