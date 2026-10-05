"""Сборка приложения FastAPI: эндпоинты платежей и Swagger под Basic-аутентификацией."""

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse

from app.api.auth import require_docs_credentials
from app.api.routes import router


async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    # Стандартный ответ повторяет входное значение; NaN/Infinity из тела запроса
    # JSON-ом не сериализуются и превращали бы 422 в 500.
    detail = [{key: error[key] for key in ("type", "loc", "msg")} for error in exc.errors()]
    return JSONResponse({"detail": detail}, status_code=422)


def create_app() -> FastAPI:
    # Встроенные страницы документации регистрируются мимо зависимостей роутеров
    # и остались бы открытыми; вместо них — свои маршруты под Basic.
    app = FastAPI(title="Payments", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.include_router(router)
    docs = APIRouter(dependencies=[Depends(require_docs_credentials)], include_in_schema=False)

    @docs.get("/openapi.json")
    async def openapi() -> dict:
        return app.openapi()

    @docs.get("/docs")
    async def swagger() -> HTMLResponse:
        return get_swagger_ui_html(openapi_url="/openapi.json", title=f"{app.title} — Swagger")

    app.include_router(docs)
    return app


app = create_app()
