"""Тесты Processor: проведение платежа и отправка webhook."""

import json
import random

import httpx
import pytest

from app.models import PaymentStatus
from app.payments import create_payment, get_payment
from app.processing import Processor
from tests.helpers import payment_body


async def _no_wait(delay: float) -> None:
    return None


def _processor(session_factory, handler) -> Processor:
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return Processor(session_factory, http, random.Random(0), _no_wait)


async def test_processor_settles_payment_and_sends_its_state(session_factory):
    created = await create_payment(session_factory, "key-1", payment_body())
    hooks = []

    def receiver(request: httpx.Request) -> httpx.Response:
        hooks.append((str(request.url), json.loads(request.content)))
        return httpx.Response(200)

    await _processor(session_factory, receiver).process(created.id)

    stored = await get_payment(session_factory, created.id)
    assert stored.status is not PaymentStatus.PENDING
    [(url, body)] = hooks
    assert url == "https://example.com/hook"
    assert body["payment_id"] == str(created.id)
    assert body["status"] == stored.status.value


async def test_redelivery_resends_webhook_without_charging_again(session_factory):
    created = await create_payment(session_factory, "key-1", payment_body())
    hooks = []

    def receiver(request: httpx.Request) -> httpx.Response:
        hooks.append(json.loads(request.content))
        return httpx.Response(200)

    processor = _processor(session_factory, receiver)
    await processor.process(created.id)
    first = await get_payment(session_factory, created.id)
    await processor.process(created.id)
    second = await get_payment(session_factory, created.id)

    assert len(hooks) == 2
    assert second.processed_at == first.processed_at
    assert hooks[0] == hooks[1]


async def test_unreachable_webhook_raises_after_payment_is_settled(session_factory):
    created = await create_payment(session_factory, "key-1", payment_body())

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("отказ в соединении", request=request)

    with pytest.raises(httpx.ConnectError):
        await _processor(session_factory, refuse).process(created.id)

    stored = await get_payment(session_factory, created.id)
    assert stored.status is not PaymentStatus.PENDING
