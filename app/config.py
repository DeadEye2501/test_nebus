"""Настройки сервиса из переменных окружения."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    api_key: str
    docs_username: str
    docs_password: str
    rabbitmq_url: str
    outbox_batch_size: int = 100
    outbox_poll_interval: float = 1.0
    retry_base_delay: float = 2.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
