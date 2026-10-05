"""Проверки relay: порядок, лимит, отметка опубликованных, сбой брокера и блокировки."""

import asyncio

import pytest
from faststream.rabbit import RabbitBroker, TestRabbitBroker
from sqlalchemy import func, select, update

from app.models import OutboxEvent
from app.relay import publish_batch
from app.topology import EXCHANGE, NEW_KEY, NEW_QUEUE
from tests.fakes import FailingBroker, RecordingBroker


async def _add_events(session_factory, payloads: list[dict]) -> None:
    async with session_factory() as session, session.begin():
        for payload in payloads:
            session.add(OutboxEvent(payload=payload))
            await session.flush()


async def _unpublished(session_factory) -> int:
    async with session_factory() as session:
        return await session.scalar(
            select(func.count()).select_from(OutboxEvent).where(OutboxEvent.published_at.is_(None))
        )


async def test_events_reach_payments_new_in_order_and_are_marked(session_factory):
    broker = RabbitBroker()
    received = []

    @broker.subscriber(NEW_QUEUE, EXCHANGE)
    async def collect(body: dict) -> None:
        received.append(body)

    await _add_events(session_factory, [{"payment_id": "a"}, {"payment_id": "b"}])
    async with TestRabbitBroker(broker) as test_broker:
        first_run = await publish_batch(session_factory, test_broker, limit=10)
        second_run = await publish_batch(session_factory, test_broker, limit=10)

    assert (first_run, second_run) == (2, 0)
    assert received == [{"payment_id": "a"}, {"payment_id": "b"}]
    assert await _unpublished(session_factory) == 0


async def test_batch_is_limited(session_factory):
    await _add_events(session_factory, [{"payment_id": "a"}, {"payment_id": "b"}])
    broker = RecordingBroker()

    assert await publish_batch(session_factory, broker, limit=1) == 1
    assert [message for message, _ in broker.published] == [{"payment_id": "a"}]
    assert await _unpublished(session_factory) == 1


async def test_failed_publish_leaves_events_for_next_run(session_factory):
    await _add_events(session_factory, [{"payment_id": "a"}])

    with pytest.raises(ConnectionError):
        await publish_batch(session_factory, FailingBroker(), limit=10)

    assert await _unpublished(session_factory) == 1


async def test_events_locked_by_another_relay_are_skipped(session_factory):
    await _add_events(session_factory, [{"payment_id": "a"}])
    broker = RecordingBroker()

    async with session_factory() as other, other.begin():
        await other.execute(select(OutboxEvent).with_for_update())
        published = await asyncio.wait_for(
            publish_batch(session_factory, broker, limit=10), timeout=5
        )

    assert published == 0
    assert broker.published == []


async def test_events_are_published_by_id_even_when_physical_order_differs(session_factory):
    await _add_events(session_factory, [{"payment_id": "a"}, {"payment_id": "b"}])
    async with session_factory() as session, session.begin():
        # UPDATE пишет новую версию строки в конец кучи: seq scan отдаст b раньше a.
        await session.execute(
            update(OutboxEvent)
            .where(OutboxEvent.payload["payment_id"].as_string() == "a")
            .values(payload={"payment_id": "a", "touched": True})
        )
    broker = RecordingBroker()

    await publish_batch(session_factory, broker, limit=1)

    assert [message for message, _ in broker.published] == [
        {"payment_id": "a", "touched": True}
    ]


async def test_publish_goes_to_payments_exchange_persistently(session_factory):
    await _add_events(session_factory, [{"payment_id": "a"}])
    broker = RecordingBroker()

    await publish_batch(session_factory, broker, limit=10)

    [(_, options)] = broker.published
    assert options["exchange"] is EXCHANGE
    assert options["routing_key"] == NEW_KEY
    assert options["persist"] is True
