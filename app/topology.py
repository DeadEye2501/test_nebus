"""Топология RabbitMQ: обменник платежей, рабочая очередь, очереди повторов и DLQ."""

from faststream.rabbit import Channel, ExchangeType, RabbitBroker, RabbitExchange, RabbitQueue

MAX_ATTEMPTS = 3
EXCHANGE = RabbitExchange("payments", type=ExchangeType.DIRECT, durable=True)
NEW_KEY = "payments.new"
DLQ_KEY = "payments.new.dlq"
NEW_QUEUE = RabbitQueue(NEW_KEY, durable=True)


def retry_key(attempt: int) -> str:
    return f"{NEW_KEY}.retry.{attempt}"


def _retry_queue(attempt: int, base_delay: float) -> RabbitQueue:
    # У очереди повтора нет потребителей: сообщение отлёживает TTL и через
    # dead-letter возвращается в payments.new.
    return RabbitQueue(
        retry_key(attempt),
        durable=True,
        arguments={
            "x-message-ttl": int(base_delay * 2 ** (attempt - 1) * 1000),
            "x-dead-letter-exchange": EXCHANGE.name,
            "x-dead-letter-routing-key": NEW_KEY,
        },
    )


async def declare(broker: RabbitBroker, base_delay: float) -> None:
    exchange = await broker.declare_exchange(EXCHANGE)
    retries = [_retry_queue(attempt, base_delay) for attempt in range(1, MAX_ATTEMPTS)]
    for queue in [NEW_QUEUE, *retries, RabbitQueue(DLQ_KEY, durable=True)]:
        declared = await broker.declare_queue(queue)
        await declared.bind(exchange, routing_key=queue.name)


def make_broker(url: str) -> RabbitBroker:
    # Без on_return_raises возврат немаршрутизируемой копии не заметили бы, и оригинал был бы потерян.
    return RabbitBroker(url, default_channel=Channel(on_return_raises=True))
