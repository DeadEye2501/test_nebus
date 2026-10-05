"""Фейковые брокеры и процессор платежей для тестов."""


class RecordingBroker:
    def __init__(self) -> None:
        self.published: list[tuple[object, dict]] = []

    async def publish(self, message: object, **options) -> None:
        self.published.append((message, options))


class FailingBroker:
    async def publish(self, message: object, **options) -> None:
        raise ConnectionError("брокер недоступен")


class StubProcessor:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list = []

    async def process(self, payment_id) -> None:
        self.calls.append(payment_id)
        if self.error is not None:
            raise self.error
