"""Подключение к PostgreSQL: асинхронный движок и фабрика сессий."""

from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

Sessions = async_sessionmaker[AsyncSession]


@lru_cache
def get_engine() -> AsyncEngine:
    return create_async_engine(get_settings().database_url)


@lru_cache
def get_sessionmaker() -> Sessions:
    return async_sessionmaker(get_engine(), expire_on_commit=False)
