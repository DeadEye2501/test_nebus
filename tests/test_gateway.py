"""Тестирование эмуляции платёжного шлюза."""

import random

from app.gateway import charge
from app.models import PaymentStatus


async def _run(times: int) -> tuple[list[float], list[PaymentStatus]]:
    rng = random.Random(42)
    delays: list[float] = []

    async def record(delay: float) -> None:
        delays.append(delay)

    outcomes = [await charge(rng, record) for _ in range(times)]
    return delays, outcomes


async def test_each_charge_waits_between_two_and_five_seconds():
    delays, _ = await _run(1000)

    assert len(delays) == 1000
    assert all(2.0 <= delay <= 5.0 for delay in delays)
    assert min(delays) < 2.2 and max(delays) > 4.8


async def test_about_nine_charges_in_ten_succeed():
    _, outcomes = await _run(10_000)

    share = outcomes.count(PaymentStatus.SUCCEEDED) / len(outcomes)
    assert 0.88 <= share <= 0.92
    assert set(outcomes) == {PaymentStatus.SUCCEEDED, PaymentStatus.FAILED}
