# Карта модулей

Собирается из кода, а не ведётся руками.
Править руками нельзя — правки затрёт следующая сборка.
Число в скобках — сколько строк занимает объявление.

## app — 14 модулей

### `app/api/auth.py` — 34 строк

Проверка доступа: ключ X-API-Key для API и Basic-аутентификация для Swagger.

Зависит от: `app.config`

- `def _same(given: str, expected: str) -> bool` (2)
- `def require_api_key(key: str | None=Security(_api_key_header)) -> None` (3)
- `def require_docs_credentials(credentials: Annotated[HTTPBasicCredentials | None, Depends(_basic)]) -> None` (10)

### `app/api/main.py` — 39 строк

Сборка приложения FastAPI: эндпоинты платежей и Swagger под Basic-аутентификацией.

Зависит от: `app.api.auth`, `app.api.routes`

- `async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse` (5)
- `def create_app() -> FastAPI` (18)
  - `async def openapi() -> dict` (2)
  - `async def swagger() -> HTMLResponse` (2)

### `app/api/routes.py` — 35 строк

Эндпоинты /api/v1/payments: создание и чтение платежа.

Зависит от: `app.api.auth`, `app.db`, `app.payments`, `app.schemas`

- `async def create(body: PaymentCreate, idempotency_key: Annotated[str, Header(min_length=1, max_length=255)]) -> PaymentAccepted` (11)
- `async def read(payment_id: uuid.UUID) -> PaymentDetail` (5)

### `app/config.py` — 22 строк

Настройки сервиса из переменных окружения.

Зависит от: —

- `class Settings(BaseSettings)` (10)
- `def get_settings() -> Settings` (2)

### `app/consumer.py` — 93 строк

Consumer очереди payments.new: проводит платёж, шлёт webhook, уводит сбои в повторы и DLQ.

Зависит от: `app.config`, `app.db`, `app.processing`, `app.schemas`, `app.topology`

- `async def handle(broker: RabbitBroker, processor: Processor, body: bytes, headers: dict) -> None` (17)
- `async def _forward(broker: RabbitBroker, body: bytes, routing_key: str, headers: dict) -> None` (8)
- `def _attempt(headers: dict) -> int` (5)
- `def _describe(exc: Exception) -> str` (2)
- `def create_app(processor: Processor, rabbitmq_url: str, retry_base_delay: float) -> FastStream` (17)
  - `async def on_new_payment(message: RabbitMessage) -> None` (2)
  - `async def declare_topology() -> None` (3)
- `async def main() -> None` (6)

### `app/db.py` — 22 строк

Подключение к PostgreSQL: асинхронный движок и фабрика сессий.

Зависит от: `app.config`

- `def get_engine() -> AsyncEngine` (2)
- `def get_sessionmaker() -> async_sessionmaker[AsyncSession]` (2)

### `app/gateway.py` — 18 строк

Эмуляция внешнего платёжного шлюза.

Зависит от: `app.models`

- `async def charge(rng: random.Random, sleep: Sleep=asyncio.sleep) -> PaymentStatus` (3)

### `app/models.py` — 79 строк

ORM-модели таблиц payments и outbox.

Зависит от: —

- `class Base(DeclarativeBase)` (2)
- `class Currency(enum.StrEnum)` (4)
- `class PaymentStatus(enum.StrEnum)` (4)
- `def _db_enum(values: type[enum.StrEnum], name: str) -> Enum` (2)
- `class Payment(Base)` (22)
- `class OutboxEvent(Base)` (11)

### `app/payments.py` — 97 строк

Операции с платежами в базе: создание, чтение, фиксация результата.

Зависит от: `app.models`, `app.schemas`

- `class IdempotencyConflict(Exception)` (2)
- `class PaymentNotFound(Exception)` (2)
- `def request_hash(body: PaymentCreate) -> str` (3)
- `async def get_payment(session_factory: Sessions, payment_id: uuid.UUID) -> Payment | None` (3)
- `async def create_payment(session_factory: Sessions, key: str, body: PaymentCreate) -> Payment` (13)
- `async def _find_by_key(session_factory: Sessions, key: str) -> Payment | None` (3)
- `async def _insert(session_factory: Sessions, key: str, body: PaymentCreate, digest: str) -> Payment` (15)
- `async def settle(session_factory: Sessions, payment_id: uuid.UUID, charge: Callable[[], Awaitable[PaymentStatus]]) -> Payment` (18)
- `async def _require(session_factory: Sessions, payment_id: uuid.UUID) -> Payment` (5)

### `app/processing.py` — 29 строк

Обработка платежа: проведение через шлюз и отправка webhook.

Зависит от: `app.gateway`, `app.payments`, `app.schemas`, `app.webhook`

- `class Processor` (12)
  - `async def process(self, payment_id: uuid.UUID) -> None` (6)

### `app/relay.py` — 61 строк

Relay outbox: публикует неопубликованные события в RabbitMQ и отмечает их.

Зависит от: `app.config`, `app.db`, `app.models`, `app.topology`

- `async def publish_batch(session_factory: async_sessionmaker[AsyncSession], broker: RabbitBroker, limit: int) -> int` (18)
- `async def run(session_factory: async_sessionmaker[AsyncSession], broker: RabbitBroker, settings: Settings) -> None` (11)
- `async def main() -> None` (7)

### `app/schemas.py` — 91 строк

Pydantic-схемы: тело запроса на платёж, ответы API и событие о новом платеже.

Зависит от: `app.models`

- `def _check_postgres_safe(value: Any) -> None` (14)
- `class PaymentCreate(BaseModel)` (17)
  - `def _to_cents(cls, value: Decimal) -> Decimal` (2)
  - `def _postgres_safe(cls, value: Any) -> Any` (3)
- `class PaymentAccepted(BaseModel)` (6)
- `class PaymentDetail(BaseModel)` (13)
- `class NewPaymentEvent(BaseModel)` (2)

### `app/topology.py` — 40 строк

Топология RabbitMQ: обменник платежей, рабочая очередь, очереди повторов и DLQ.

Зависит от: —

- `def retry_key(attempt: int) -> str` (2)
- `def _retry_queue(attempt: int, base_delay: float) -> RabbitQueue` (12)
- `async def declare(broker: RabbitBroker, base_delay: float) -> None` (6)
- `def make_broker(url: str) -> RabbitBroker` (3)

### `app/webhook.py` — 13 строк

Отправка webhook-уведомления о результате платежа.

Зависит от: —

- `class WebhookError(Exception)` (2)
- `async def send(client: httpx.AsyncClient, url: str, body: dict) -> None` (4)

## migrations — 2 модулей

### `migrations/env.py` — 25 строк

Окружение Alembic: применяет миграции через асинхронный движок приложения.

Зависит от: `app.db`, `app.models`

- `def _run(connection: Connection) -> None` (4)
- `async def _run_async() -> None` (5)

### `migrations/versions/0001_payments_and_outbox.py` — 48 строк

Таблицы payments и outbox.

Зависит от: —

- `def upgrade() -> None` (31)
- `def downgrade() -> None` (5)

## tests — 12 модулей

### `tests/conftest.py` — 62 строк

Общие фикстуры: схема тестовой БД из миграций и чистые таблицы перед каждым тестом.

Зависит от: `app.api.main`, `app.config`, `app.db`

- `def pytest_collection_modifyitems(items: list[pytest.Item]) -> None` (7)
- `async def _schema()` (11)
- `async def _clean_tables(_schema)` (3)
- `def session_factory()` (2)
- `async def session(session_factory)` (3)
- `async def client()` (4)

### `tests/fakes.py` — 25 строк

Фейковые брокеры и процессор платежей для тестов.

Зависит от: —

- `class RecordingBroker` (6)
  - `async def publish(self, message: object, **options) -> None` (2)
- `class FailingBroker` (3)
  - `async def publish(self, message: object, **options) -> None` (2)
- `class StubProcessor` (9)
  - `async def process(self, payment_id) -> None` (4)

### `tests/helpers.py` — 32 строк

Построители тестовых данных.

Зависит от: `app.models`, `app.schemas`

- `def payment_row(**overrides) -> Payment` (12)
- `def payment_body(**overrides) -> PaymentCreate` (9)

### `tests/test_api_docs.py` — 37 строк

Проверки Swagger: доступ только под Basic, схема с X-API-Key, ReDoc не опубликован.

Зависит от: —

Тестов: 4


### `tests/test_api_payments.py` — 147 строк

Проверки HTTP API платежей: создание, чтение, идемпотентность, ключ доступа и валидация.

Зависит от: —

Тестов: 11

- `def _headers(idempotency_key: str='key-1') -> dict[str, str]` (2)

### `tests/test_consumer.py` — 215 строк

Тесты consumer: обработка, повторы, DLQ и сборка платежа процессором.

Зависит от: `app.consumer`, `app.models`, `app.payments`, `app.processing`, `app.topology`, `app.webhook`, `tests.fakes`, `tests.helpers`

Тестов: 12

- `def _body(payment_id: uuid.UUID) -> bytes` (2)
- `async def _no_wait(delay: float) -> None` (2)
- `def _processor(session_factory, handler) -> Processor` (3)

### `tests/test_gateway.py` — 33 строк

Тестирование эмуляции платёжного шлюза.

Зависит от: `app.gateway`, `app.models`

Тестов: 2

- `async def _run(times: int) -> tuple[list[float], list[PaymentStatus]]` (9)
  - `async def record(delay: float) -> None` (2)

### `tests/test_payments.py` — 109 строк

Тесты создания платежа с идемпотентностью и outbox и чтения платежа.

Зависит от: `app`, `app.models`, `app.payments`, `tests.helpers`

Тестов: 8

- `async def _count(session_factory, model) -> int` (3)
- `def _miss_first_lookup(monkeypatch)` (10)
  - `async def find(session_factory, key)` (3)

### `tests/test_relay.py` — 106 строк

Проверки relay: порядок, лимит, отметка опубликованных, сбой брокера и блокировки.

Зависит от: `app.models`, `app.relay`, `app.topology`, `tests.fakes`

Тестов: 6

- `async def _add_events(session_factory, payloads: list[dict]) -> None` (5)
- `async def _unpublished(session_factory) -> int` (5)

### `tests/test_schema.py` — 59 строк

Поведение схемы БД: значения по умолчанию, ограничения, порядок outbox.

Зависит от: `app.db`, `app.models`, `tests.helpers`

Тестов: 5


### `tests/test_settle.py` — 62 строк

Тесты фиксации результата обработки платежа.

Зависит от: `app.models`, `app.payments`, `tests.helpers`

Тестов: 4

- `def _gateway(outcome: PaymentStatus, calls: list[str])` (6)
  - `async def charge() -> PaymentStatus` (3)

### `tests/test_webhook.py` — 45 строк

Тестирование отправки webhook-уведомления о результате платежа.

Зависит от: `app.webhook`

Тестов: 3

- `def _client(handler) -> httpx.AsyncClient` (2)

## Абстракции с одной реализацией

Нет.
