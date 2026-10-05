"""Поведение схемы БД: значения по умолчанию, ограничения, порядок outbox."""

from decimal import Decimal

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy.exc import IntegrityError

from app.db import get_engine
from app.models import Base, OutboxEvent, PaymentStatus
from tests.helpers import payment_row


async def test_new_payment_is_pending_with_creation_time(session):
    payment = payment_row()
    session.add(payment)
    await session.commit()

    assert payment.status is PaymentStatus.PENDING
    assert payment.created_at is not None
    assert payment.processed_at is None


async def test_second_payment_with_same_idempotency_key_is_rejected(session):
    session.add(payment_row(idempotency_key="same"))
    await session.commit()
    session.add(payment_row(idempotency_key="same"))

    with pytest.raises(IntegrityError):
        await session.commit()


async def test_non_positive_amount_is_rejected(session):
    session.add(payment_row(amount=Decimal(0)))

    with pytest.raises(IntegrityError):
        await session.commit()


async def test_outbox_events_get_increasing_ids_and_start_unpublished(session):
    first = OutboxEvent(payload={"payment_id": "a"})
    second = OutboxEvent(payload={"payment_id": "b"})
    session.add(first)
    await session.flush()
    session.add(second)
    await session.commit()

    assert second.id > first.id
    assert first.published_at is None


async def test_models_match_migrated_schema():
    def drift(sync_connection):
        context = MigrationContext.configure(sync_connection, opts={"compare_server_default": True})
        return compare_metadata(context, Base.metadata)

    async with get_engine().connect() as connection:
        assert await connection.run_sync(drift) == []
