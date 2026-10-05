"""Relay outbox: перенос неопубликованных событий в RabbitMQ."""

import asyncio
import logging

from faststream.rabbit import RabbitBroker
from sqlalchemy import func, select

from app.config import Settings, get_settings
from app.db import Sessions, get_sessionmaker
from app.models import OutboxEvent
from app.topology import EXCHANGE, NEW_KEY, declare, make_broker

logger = logging.getLogger(__name__)


async def publish_batch(session_factory: Sessions, broker: RabbitBroker, limit: int) -> int:
    async with session_factory() as session, session.begin():
        events = (
            await session.scalars(
                select(OutboxEvent)
                .where(OutboxEvent.published_at.is_(None))
                .order_by(OutboxEvent.id)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).all()
        for event in events:
            await broker.publish(
                event.payload, exchange=EXCHANGE, routing_key=NEW_KEY, persist=True
            )
            event.published_at = func.now()
    return len(events)


async def run(session_factory: Sessions, broker: RabbitBroker, settings: Settings) -> None:
    while True:
        try:
            published = await publish_batch(session_factory, broker, settings.outbox_batch_size)
        except Exception:
            logger.exception("Публикация из outbox не удалась, повтор на следующей итерации")
            published = 0
        if not published:
            await asyncio.sleep(settings.outbox_poll_interval)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    broker = make_broker(settings.rabbitmq_url)
    await broker.connect()
    await declare(broker, settings.retry_base_delay)
    await run(get_sessionmaker(), broker, settings)


if __name__ == "__main__":
    asyncio.run(main())
