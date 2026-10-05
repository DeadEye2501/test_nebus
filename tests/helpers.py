"""Построители тестовых данных."""

import uuid
from decimal import Decimal

from app.models import Currency, Payment
from app.schemas import PaymentCreate


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


def payment_body(**overrides) -> PaymentCreate:
    fields = {
        "amount": "100.50",
        "currency": "RUB",
        "description": "Заказ 42",
        "metadata": {"order_id": 42, "source": "web"},
        "webhook_url": "https://example.com/hook",
    } | overrides
    return PaymentCreate.model_validate(fields)
