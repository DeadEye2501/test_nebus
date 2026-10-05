"""Эмуляция внешнего платёжного шлюза."""

import asyncio
import random
from collections.abc import Awaitable, Callable

from app.models import PaymentStatus

SUCCESS_RATE = 0.9
MIN_DELAY = 2.0
MAX_DELAY = 5.0

Sleep = Callable[[float], Awaitable[None]]


async def charge(rng: random.Random, sleep: Sleep = asyncio.sleep) -> PaymentStatus:
    await sleep(rng.uniform(MIN_DELAY, MAX_DELAY))
    return PaymentStatus.SUCCEEDED if rng.random() < SUCCESS_RATE else PaymentStatus.FAILED
