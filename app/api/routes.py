"""Эндпоинты /api/v1/payments: создание и чтение платежа."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.api.auth import require_api_key
from app.db import get_sessionmaker
from app.payments import IdempotencyConflict, create_payment, get_payment
from app.schemas import PaymentAccepted, PaymentCreate, PaymentDetail

router = APIRouter(prefix="/api/v1/payments", dependencies=[Depends(require_api_key)])


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=PaymentAccepted)
async def create(
    body: PaymentCreate,
    idempotency_key: Annotated[str, Header(min_length=1, max_length=255)],
) -> PaymentAccepted:
    try:
        payment = await create_payment(get_sessionmaker(), idempotency_key, body)
    except IdempotencyConflict as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Idempotency-Key уже использован с другим телом запроса"
        ) from exc
    return PaymentAccepted.model_validate(payment)


@router.get("/{payment_id}", response_model=PaymentDetail)
async def read(payment_id: uuid.UUID) -> PaymentDetail:
    payment = await get_payment(get_sessionmaker(), payment_id)
    if payment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Платёж не найден")
    return PaymentDetail.model_validate(payment)
