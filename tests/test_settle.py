"""Тесты фиксации результата обработки платежа."""

import uuid

import pytest
from sqlalchemy import update

from app.models import Payment, PaymentStatus
from app.payments import PaymentNotFound, create_payment, settle
from tests.helpers import payment_body


def _gateway(outcome: PaymentStatus, calls: list[str]):
    async def charge() -> PaymentStatus:
        calls.append("charge")
        return outcome

    return charge


@pytest.mark.parametrize("outcome", [PaymentStatus.SUCCEEDED, PaymentStatus.FAILED])
async def test_pending_payment_gets_gateway_outcome_and_processing_time(session_factory, outcome):
    created = await create_payment(session_factory, "key-1", payment_body())
    calls: list[str] = []

    settled = await settle(session_factory, created.id, _gateway(outcome, calls))

    assert calls == ["charge"]
    assert settled.status is outcome
    assert settled.processed_at is not None


async def test_final_payment_is_not_charged_again(session_factory):
    created = await create_payment(session_factory, "key-1", payment_body())
    first = await settle(session_factory, created.id, _gateway(PaymentStatus.SUCCEEDED, []))
    calls: list[str] = []

    second = await settle(session_factory, created.id, _gateway(PaymentStatus.FAILED, calls))

    assert calls == []
    assert second.status is PaymentStatus.SUCCEEDED
    assert second.processed_at == first.processed_at


async def test_outcome_written_by_another_worker_wins(session_factory):
    created = await create_payment(session_factory, "key-1", payment_body())

    async def racing_charge() -> PaymentStatus:
        async with session_factory() as session, session.begin():
            await session.execute(
                update(Payment).where(Payment.id == created.id).values(status=PaymentStatus.FAILED)
            )
        return PaymentStatus.SUCCEEDED

    settled = await settle(session_factory, created.id, racing_charge)

    assert settled.status is PaymentStatus.FAILED


async def test_unknown_payment_raises(session_factory):
    with pytest.raises(PaymentNotFound):
        await settle(session_factory, uuid.uuid4(), _gateway(PaymentStatus.SUCCEEDED, []))
