"""Pydantic-схемы: тело запроса на платёж, ответы API и событие о новом платеже."""

import math
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import (
    AliasChoices,
    AnyUrl,
    BaseModel,
    ConfigDict,
    Field,
    UrlConstraints,
    field_validator,
)

from app.models import Currency, PaymentStatus

CENT = Decimal("0.01")

WebhookUrl = Annotated[AnyUrl, UrlConstraints(max_length=2048, allowed_schemes=["http", "https"])]

# Схемы ответа строятся из ORM (атрибуты id и meta) и повторно валидируются FastAPI
# из собственного дампа (ключи payment_id и metadata) — поэтому принимаются оба имени.
# meta стоит первым: у ORM-модели атрибут metadata — это MetaData SQLAlchemy.
PaymentId = Annotated[uuid.UUID, Field(validation_alias=AliasChoices("id", "payment_id"))]
Metadata = Annotated[dict[str, Any], Field(validation_alias=AliasChoices("meta", "metadata"))]


def _check_postgres_safe(value: Any) -> None:
    # Postgres не хранит NUL в text/jsonb и не принимает NaN/Infinity в jsonb:
    # без проверки такой ввод дошёл бы до БД и вернулся бы как 500.
    if isinstance(value, str) and "\x00" in value:
        raise ValueError("NUL-символ не допускается")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("NaN и Infinity не допускаются")
    if isinstance(value, dict):
        for key, item in value.items():
            _check_postgres_safe(key)
            _check_postgres_safe(item)
    elif isinstance(value, list):
        for item in value:
            _check_postgres_safe(item)


class PaymentCreate(BaseModel):
    amount: Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=2)]
    currency: Currency
    description: Annotated[str, Field(min_length=1, max_length=500)]
    metadata: dict[str, Any] = Field(default_factory=dict)
    webhook_url: WebhookUrl

    @field_validator("amount")
    @classmethod
    def _to_cents(cls, value: Decimal) -> Decimal:
        return value.quantize(CENT)

    @field_validator("description", "metadata")
    @classmethod
    def _postgres_safe(cls, value: Any) -> Any:
        _check_postgres_safe(value)
        return value


class PaymentAccepted(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    payment_id: PaymentId
    status: PaymentStatus
    created_at: datetime


class PaymentDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    payment_id: PaymentId
    amount: Decimal
    currency: Currency
    description: str
    metadata: Metadata
    status: PaymentStatus
    idempotency_key: str
    webhook_url: str
    created_at: datetime
    processed_at: datetime | None


class NewPaymentEvent(BaseModel):
    payment_id: uuid.UUID
