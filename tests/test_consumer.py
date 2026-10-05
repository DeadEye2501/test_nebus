"""Тесты consumer: обработка, повторы, DLQ и сборка платежа процессором."""

import json
import random
import uuid

import httpx
import pytest
from faststream.exceptions import NackMessage
from faststream.rabbit import RabbitQueue, TestRabbitBroker
from faststream.rabbit.annotations import RabbitMessage

from app.consumer import create_app, handle
from app.models import PaymentStatus
from app.payments import create_payment, get_payment
from app.processing import Processor
from app.topology import DLQ_KEY, EXCHANGE, NEW_KEY, retry_key
from app.webhook import WebhookError
from tests.fakes import FailingBroker, RecordingBroker, StubProcessor
from tests.helpers import payment_body


def _body(payment_id: uuid.UUID) -> bytes:
    return json.dumps({"payment_id": str(payment_id)}).encode()


async def _no_wait(delay: float) -> None:
    return None


async def test_successful_processing_publishes_nothing():
    payment_id = uuid.uuid4()
    broker, processor = RecordingBroker(), StubProcessor()

    await handle(broker, processor, _body(payment_id), {})

    assert processor.calls == [payment_id]
    assert broker.published == []


@pytest.mark.parametrize(
    ("headers", "route", "next_attempt"),
    [({}, retry_key(1), 2), ({"x-attempt": 2}, retry_key(2), 3)],
)
async def test_failure_goes_to_next_retry_queue(headers, route, next_attempt):
    body = _body(uuid.uuid4())
    broker = RecordingBroker()

    await handle(broker, StubProcessor(WebhookError("500")), body, headers)

    [(message, options)] = broker.published
    assert message == body
    assert options["routing_key"] == route
    assert options["headers"]["x-attempt"] == next_attempt


async def test_third_failure_goes_to_dlq_with_error():
    body = _body(uuid.uuid4())
    broker = RecordingBroker()

    await handle(broker, StubProcessor(RuntimeError("boom")), body, {"x-attempt": 3})

    [(message, options)] = broker.published
    assert message == body
    assert options["routing_key"] == DLQ_KEY
    assert options["headers"]["x-error"] == "RuntimeError: boom"


@pytest.mark.parametrize("body", [b"not json", b'{"payment_id": "nope"}', b"[]"])
async def test_malformed_message_goes_straight_to_dlq(body):
    broker, processor = RecordingBroker(), StubProcessor()

    await handle(broker, processor, body, {})

    assert processor.calls == []
    [(message, options)] = broker.published
    assert message == body
    assert options["routing_key"] == DLQ_KEY
    assert "ValidationError" in options["headers"]["x-error"]


async def test_failed_forward_nacks_original_message():
    with pytest.raises(NackMessage) as raised:
        await handle(FailingBroker(), StubProcessor(RuntimeError("boom")), _body(uuid.uuid4()), {})

    assert raised.value.extra_options == {"requeue": True}


@pytest.mark.parametrize("attempt", ["abc", 0, -1])
async def test_invalid_attempt_header_goes_straight_to_dlq(attempt):
    body = _body(uuid.uuid4())
    broker, processor = RecordingBroker(), StubProcessor()

    await handle(broker, processor, body, {"x-attempt": attempt})

    assert processor.calls == []
    [(message, options)] = broker.published
    assert message == body
    assert options["routing_key"] == DLQ_KEY
    assert "ValueError" in options["headers"]["x-error"]


async def test_message_from_payments_new_reaches_processor_and_failure_reaches_retry_queue():
    payment_id = uuid.uuid4()
    processor = StubProcessor(RuntimeError("boom"))
    app = create_app(processor, "amqp://guest:guest@localhost:5672/", 2.0)
    retried = []

    @app.broker.subscriber(RabbitQueue(retry_key(1)), EXCHANGE)
    async def collect(message: RabbitMessage) -> None:
        retried.append(message.headers.get("x-attempt"))

    async with TestRabbitBroker(app.broker) as broker:
        await broker.publish({"payment_id": str(payment_id)}, exchange=EXCHANGE, routing_key=NEW_KEY)

    assert processor.calls == [payment_id]
    assert retried == [2]


@pytest.mark.parametrize(
    ("header", "route", "next_attempt"),
    [(2, retry_key(2), 3), ("2", retry_key(2), 3)],
)
async def test_attempt_header_from_queue_reaches_handler(header, route, next_attempt):
    processor = StubProcessor(RuntimeError("boom"))
    app = create_app(processor, "amqp://guest:guest@localhost:5672/", 2.0)
    retried = []

    @app.broker.subscriber(RabbitQueue(route), EXCHANGE)
    async def collect(message: RabbitMessage) -> None:
        retried.append(message.headers.get("x-attempt"))

    async with TestRabbitBroker(app.broker) as broker:
        await broker.publish(
            {"payment_id": str(uuid.uuid4())},
            exchange=EXCHANGE,
            routing_key=NEW_KEY,
            headers={"x-attempt": header},
        )

    assert retried == [next_attempt]


async def test_startup_connects_broker_and_declares_topology(monkeypatch):
    app = create_app(StubProcessor(), "amqp://guest:guest@localhost:5672/", 3.5)
    events = []

    async def connect() -> None:
        events.append("connect")

    async def declare(broker, base_delay) -> None:
        events.append(("declare", broker, base_delay))

    monkeypatch.setattr(app.broker, "connect", connect)
    monkeypatch.setattr("app.consumer.declare", declare)

    async with app._start_hooks_context():
        pass

    assert events == ["connect", ("declare", app.broker, 3.5)]


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
