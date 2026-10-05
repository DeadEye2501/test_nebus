"""Обработка платежа: проведение через шлюз с последующим webhook."""

import asyncio
import random
import uuid
from dataclasses import dataclass

import httpx

from app.db import Sessions
from app.gateway import Sleep, charge
from app.payments import settle
from app.schemas import PaymentDetail
from app.webhook import send


@dataclass(frozen=True)
class Processor:
    session_factory: Sessions
    http: httpx.AsyncClient
    rng: random.Random
    sleep: Sleep = asyncio.sleep

    async def process(self, payment_id: uuid.UUID) -> None:
        payment = await settle(
            self.session_factory, payment_id, lambda: charge(self.rng, self.sleep)
        )
        body = PaymentDetail.model_validate(payment).model_dump(mode="json")
        await send(self.http, payment.webhook_url, body)
