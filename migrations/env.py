"""Окружение Alembic: применяет миграции через асинхронный движок приложения."""

import asyncio

from alembic import context
from sqlalchemy.engine import Connection

from app.db import get_engine
from app.models import Base


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


async def _run_async() -> None:
    engine = get_engine()
    async with engine.connect() as connection:
        await connection.run_sync(_run)
    await engine.dispose()


asyncio.run(_run_async())
