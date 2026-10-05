"""Операции с платежами в базе: создание, чтение, фиксация результата."""

import hashlib
import json
import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.db import Sessions
from app.models import OutboxEvent, Payment, PaymentStatus
from app.schemas import NewPaymentEvent, PaymentCreate


class IdempotencyConflict(Exception):
    """Ключ идемпотентности уже использован с другим телом запроса."""


class PaymentNotFound(Exception):
    """Платежа с таким id нет в базе."""


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


async def settle(
    session_factory: Sessions,
    payment_id: uuid.UUID,
    charge: Callable[[], Awaitable[PaymentStatus]],
) -> Payment:
    payment = await _require(session_factory, payment_id)
    if payment.status is not PaymentStatus.PENDING:
        return payment
    # Транзакция не держится открытой на время ответа шлюза: результат пишется
    # условным апдейтом, и если платёж уже провёл другой обработчик, побеждает он.
    outcome = await charge()
    async with session_factory() as session, session.begin():
        await session.execute(
            update(Payment)
            .where(Payment.id == payment_id, Payment.status == PaymentStatus.PENDING)
            .values(status=outcome, processed_at=func.now())
        )
    return await _require(session_factory, payment_id)


async def _require(session_factory: Sessions, payment_id: uuid.UUID) -> Payment:
    payment = await get_payment(session_factory, payment_id)
    if payment is None:
        raise PaymentNotFound(payment_id)
    return payment
