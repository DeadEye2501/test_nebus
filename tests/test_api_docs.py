"""Проверки Swagger: доступ только под Basic, схема с X-API-Key, ReDoc не опубликован."""

import pytest

DOCS_AUTH = ("docs", "docs-secret")


@pytest.mark.parametrize("path", ["/docs", "/openapi.json"])
@pytest.mark.parametrize("auth", [None, ("docs", "wrong"), ("someone", "docs-secret")])
async def test_docs_require_basic_credentials(client, path, auth):
    response = await client.get(path, auth=auth)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Basic"


async def test_swagger_page_opens_with_credentials(client):
    response = await client.get("/docs", auth=DOCS_AUTH)

    assert response.status_code == 200
    assert "swagger-ui" in response.text
    assert "/openapi.json" in response.text


async def test_schema_lists_payment_endpoints_and_api_key_scheme(client):
    response = await client.get("/openapi.json", auth=DOCS_AUTH)

    schema = response.json()
    assert set(schema["paths"]) == {"/api/v1/payments", "/api/v1/payments/{payment_id}"}
    schemes = schema["components"]["securitySchemes"].values()
    assert {"type": "apiKey", "in": "header", "name": "X-API-Key"} in schemes


async def test_redoc_is_not_published(client):
    response = await client.get("/redoc", auth=DOCS_AUTH)

    assert response.status_code == 404
