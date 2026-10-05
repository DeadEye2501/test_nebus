"""Общие фикстуры: схема тестовой БД из миграций и чистые таблицы перед каждым тестом."""

import asyncio
import subprocess
import sys

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.config import get_settings
from app.db import get_engine, get_sessionmaker


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    # Движок кэшируется на процесс, а соединения asyncpg привязаны к циклу событий:
    # все тесты обязаны жить в одном цикле сессии.
    session_loop = pytest.mark.asyncio(loop_scope="session")
    for item in items:
        if pytest_asyncio.is_async_test(item):
            item.add_marker(session_loop, append=False)


@pytest.fixture(scope="session", autouse=True)
async def _schema():
    database = make_url(get_settings().database_url).database
    if not (database or "").endswith("_test"):
        pytest.exit(f"Тесты стирают схему; база {database!r} не оканчивается на _test", returncode=2)
    async with get_engine().begin() as connection:
        await connection.execute(text("DROP SCHEMA public CASCADE"))
        await connection.execute(text("CREATE SCHEMA public"))
    command = [sys.executable, "-m", "alembic", "upgrade", "head"]
    await asyncio.to_thread(subprocess.run, command, check=True)
    yield
    await get_engine().dispose()


@pytest.fixture(autouse=True)
async def _clean_tables(_schema):
    async with get_engine().begin() as connection:
        await connection.execute(text("TRUNCATE payments, outbox RESTART IDENTITY"))


@pytest.fixture
def session_factory():
    return get_sessionmaker()


@pytest.fixture
async def session(session_factory):
    async with session_factory() as opened:
        yield opened
