"""Фейковые брокеры для тестов публикации."""


class RecordingBroker:
    def __init__(self) -> None:
        self.published: list[tuple[object, dict]] = []

    async def publish(self, message: object, **options) -> None:
        self.published.append((message, options))


class FailingBroker:
    async def publish(self, message: object, **options) -> None:
        raise ConnectionError("брокер недоступен")
