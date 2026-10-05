"""Тестирование отправки webhook-уведомления о результате платежа."""

import json

import httpx
import pytest

from app.webhook import WebhookError, send

URL = "https://example.com/hook"


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.parametrize("code", [200, 204])
async def test_body_is_posted_as_json_and_2xx_is_success(code):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, str(request.url), json.loads(request.content)))
        return httpx.Response(code)

    async with _client(handler) as client:
        await send(client, URL, {"payment_id": "p", "status": "succeeded"})

    assert seen == [("POST", URL, {"payment_id": "p", "status": "succeeded"})]


@pytest.mark.parametrize("code", [302, 404, 500])
async def test_non_2xx_raises(code):
    async with _client(lambda request: httpx.Response(code)) as client:
        with pytest.raises(WebhookError):
            await send(client, URL, {})


@pytest.mark.parametrize("error", [httpx.ConnectError, httpx.ReadTimeout])
async def test_transport_errors_propagate(error):
    def handler(request: httpx.Request) -> httpx.Response:
        raise error("нет ответа", request=request)

    async with _client(handler) as client:
        with pytest.raises(error):
            await send(client, URL, {})
