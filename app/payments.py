"""Операции с платежами в базе: создание с идемпотентностью и событием outbox, чтение."""

import hashlib
import json
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import OutboxEvent, Payment
from app.schemas import NewPaymentEvent, PaymentCreate

Sessions = async_sessionmaker[AsyncSession]


class IdempotencyConflict(Exception):
    """Ключ идемпотентности уже использован с другим телом запроса."""


def request_hash(body: PaymentCreate) -> str:
    canonical = json.dumps(body.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


async def get_payment(session_factory: Sessions, payment_id: uuid.UUID) -> Payment | None:
    async with session_factory() as session:
        return await session.get(Payment, payment_id)


async def create_payment(session_factory: Sessions, key: str, body: PaymentCreate) -> Payment:
    digest = request_hash(body)
    existing = await _find_by_key(session_factory, key)
    if existing is None:
        try:
            return await _insert(session_factory, key, body, digest)
        except IntegrityError:
            existing = await _find_by_key(session_factory, key)
            if existing is None:
                raise
    if existing.request_hash != digest:
        raise IdempotencyConflict(key)
    return existing


async def _find_by_key(session_factory: Sessions, key: str) -> Payment | None:
    async with session_factory() as session:
        return await session.scalar(select(Payment).where(Payment.idempotency_key == key))


async def _insert(session_factory: Sessions, key: str, body: PaymentCreate, digest: str) -> Payment:
    payment = Payment(
        id=uuid.uuid4(),
        amount=body.amount,
        currency=body.currency,
        description=body.description,
        meta=body.metadata,
        idempotency_key=key,
        request_hash=digest,
        webhook_url=str(body.webhook_url),
    )
    event = OutboxEvent(payload=NewPaymentEvent(payment_id=payment.id).model_dump(mode="json"))
    async with session_factory() as session, session.begin():
        session.add_all([payment, event])
    return payment
