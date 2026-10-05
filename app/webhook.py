"""Отправка webhook-уведомления о результате платежа."""

import httpx


class WebhookError(Exception):
    """Получатель webhook ответил кодом вне 2xx."""


async def send(client: httpx.AsyncClient, url: str, body: dict) -> None:
    response = await client.post(url, json=body)
    if not response.is_success:
        raise WebhookError(f"{url} ответил {response.status_code}")
