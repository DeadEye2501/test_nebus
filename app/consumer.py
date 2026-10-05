"""Consumer очереди payments.new: проводит платёж, шлёт webhook, уводит сбои в повторы и DLQ."""

import asyncio
import logging
import random

import httpx
from faststream import FastStream
from faststream.exceptions import NackMessage
from faststream.rabbit import RabbitBroker
from faststream.rabbit.annotations import RabbitMessage

from app.config import get_settings
from app.db import get_sessionmaker
from app.processing import Processor
from app.schemas import NewPaymentEvent
from app.topology import DLQ_KEY, EXCHANGE, MAX_ATTEMPTS, NEW_QUEUE, declare, make_broker, retry_key

logger = logging.getLogger(__name__)

ATTEMPT_HEADER = "x-attempt"
ERROR_HEADER = "x-error"


async def handle(broker: RabbitBroker, processor: Processor, body: bytes, headers: dict) -> None:
    try:
        attempt = _attempt(headers)
        event = NewPaymentEvent.model_validate_json(body)
    except ValueError as exc:
        logger.exception("Битое сообщение, в DLQ без повторов")
        await _forward(broker, body, DLQ_KEY, {ERROR_HEADER: _describe(exc)})
        return
    try:
        await processor.process(event.payment_id)
    except Exception as exc:
        logger.exception("Платёж %s: попытка %s из %s не удалась", event.payment_id, attempt, MAX_ATTEMPTS)
        if attempt >= MAX_ATTEMPTS:
            failure = {ATTEMPT_HEADER: attempt, ERROR_HEADER: _describe(exc)}
            await _forward(broker, body, DLQ_KEY, failure)
        else:
            await _forward(broker, body, retry_key(attempt), {ATTEMPT_HEADER: attempt + 1})


async def _forward(broker: RabbitBroker, body: bytes, routing_key: str, headers: dict) -> None:
    try:
        await broker.publish(
            body, exchange=EXCHANGE, routing_key=routing_key, headers=headers, persist=True
        )
    except Exception as exc:
        logger.exception("Не удалось переложить сообщение в %s, возвращаю в очередь", routing_key)
        raise NackMessage(requeue=True) from exc


def _attempt(headers: dict) -> int:
    attempt = int(headers.get(ATTEMPT_HEADER, 1))
    if attempt < 1:
        raise ValueError(f"Номер попытки {attempt} меньше 1")
    return attempt


def _describe(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


def create_app(processor: Processor, rabbitmq_url: str, retry_base_delay: float) -> FastStream:
    broker = make_broker(rabbitmq_url)

    @broker.subscriber(NEW_QUEUE, EXCHANGE)
    async def on_new_payment(message: RabbitMessage) -> None:
        await handle(broker, processor, message.body, message.headers)

    app = FastStream(broker)

    # Очереди повторов и DLQ объявляются до старта подписчика: иначе первая же
    # неудача ушла бы в обменник без привязанной очереди.
    @app.on_startup
    async def declare_topology() -> None:
        await broker.connect()
        await declare(broker, retry_base_delay)

    return app


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    async with httpx.AsyncClient(timeout=settings.webhook_timeout) as http:
        processor = Processor(get_sessionmaker(), http, random.Random())
        await create_app(processor, settings.rabbitmq_url, settings.retry_base_delay).run()


if __name__ == "__main__":
    asyncio.run(main())
