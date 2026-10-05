"""Настройки сервиса из переменных окружения."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    api_key: str
    docs_username: str
    docs_password: str


@lru_cache
def get_settings() -> Settings:
    return Settings()
