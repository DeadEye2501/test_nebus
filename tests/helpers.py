"""Построители тестовых данных."""

import uuid
from decimal import Decimal

from app.models import Currency, Payment


def payment_row(**overrides) -> Payment:
    fields = {
        "id": uuid.uuid4(),
        "amount": Decimal("10.00"),
        "currency": Currency.RUB,
        "description": "Тест",
        "meta": {},
        "idempotency_key": str(uuid.uuid4()),
        "request_hash": "0" * 64,
        "webhook_url": "https://example.com/hook",
    } | overrides
    return Payment(**fields)
