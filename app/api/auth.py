"""Проверка доступа: ключ X-API-Key для API и Basic-аутентификация для Swagger."""

import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPBasic, HTTPBasicCredentials

from app.config import get_settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_basic = HTTPBasic(auto_error=False)
_BASIC_CHALLENGE = {"WWW-Authenticate": "Basic"}


def _same(given: str, expected: str) -> bool:
    return secrets.compare_digest(given.encode(), expected.encode())


def require_api_key(key: str | None = Security(_api_key_header)) -> None:
    if key is None or not _same(key, get_settings().api_key):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный или отсутствующий X-API-Key")


def require_docs_credentials(
    credentials: Annotated[HTTPBasicCredentials | None, Depends(_basic)],
) -> None:
    settings = get_settings()
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, headers=_BASIC_CHALLENGE)
    user_ok = _same(credentials.username, settings.docs_username)
    password_ok = _same(credentials.password, settings.docs_password)
    if not (user_ok and password_ok):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, headers=_BASIC_CHALLENGE)
