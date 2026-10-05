# Карта модулей

Собирается из кода, а не ведётся руками.
Править руками нельзя — правки затрёт следующая сборка.
Число в скобках — сколько строк занимает объявление.

## app — 5 модулей

### `app/config.py` — 14 строк

Настройки сервиса из переменных окружения.

Зависит от: —

- `class Settings(BaseSettings)` (2)
- `def get_settings() -> Settings` (2)

### `app/db.py` — 22 строк

Подключение к PostgreSQL: асинхронный движок и фабрика сессий.

Зависит от: `app.config`

- `def get_engine() -> AsyncEngine` (2)
- `def get_sessionmaker() -> async_sessionmaker[AsyncSession]` (2)

### `app/models.py` — 79 строк

ORM-модели таблиц payments и outbox.

Зависит от: —

- `class Base(DeclarativeBase)` (2)
- `class Currency(enum.StrEnum)` (4)
- `class PaymentStatus(enum.StrEnum)` (4)
- `def _db_enum(values: type[enum.StrEnum], name: str) -> Enum` (2)
- `class Payment(Base)` (22)
- `class OutboxEvent(Base)` (11)

### `app/payments.py` — 65 строк

Операции с платежами в базе: создание с идемпотентностью и событием outbox, чтение.

Зависит от: `app.models`, `app.schemas`

- `class IdempotencyConflict(Exception)` (2)
- `def request_hash(body: PaymentCreate) -> str` (3)
- `async def get_payment(session_factory: Sessions, payment_id: uuid.UUID) -> Payment | None` (3)
- `async def create_payment(session_factory: Sessions, key: str, body: PaymentCreate) -> Payment` (13)
- `async def _find_by_key(session_factory: Sessions, key: str) -> Payment | None` (3)
- `async def _insert(session_factory: Sessions, key: str, body: PaymentCreate, digest: str) -> Payment` (15)

### `app/schemas.py` — 68 строк

Pydantic-схемы: тело запроса на платёж, ответы API и событие о новом платеже.

Зависит от: `app.models`

- `class PaymentCreate(BaseModel)` (11)
  - `def _to_cents(cls, value: Decimal) -> Decimal` (2)
- `class PaymentAccepted(BaseModel)` (6)
- `class PaymentDetail(BaseModel)` (13)
- `class NewPaymentEvent(BaseModel)` (2)

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

## tests — 4 модулей

### `tests/conftest.py` — 53 строк

Общие фикстуры: схема тестовой БД из миграций и чистые таблицы перед каждым тестом.

Зависит от: `app.config`, `app.db`

- `def pytest_collection_modifyitems(items: list[pytest.Item]) -> None` (7)
- `async def _schema()` (11)
- `async def _clean_tables(_schema)` (3)
- `def session_factory()` (2)
- `async def session(session_factory)` (3)

### `tests/helpers.py` — 32 строк

Построители тестовых данных.

Зависит от: `app.models`, `app.schemas`

- `def payment_row(**overrides) -> Payment` (12)
- `def payment_body(**overrides) -> PaymentCreate` (9)

### `tests/test_payments.py` — 109 строк

Тесты создания платежа с идемпотентностью и outbox и чтения платежа.

Зависит от: `app`, `app.models`, `app.payments`, `tests.helpers`

Тестов: 8

- `async def _count(session_factory, model) -> int` (3)
- `def _miss_first_lookup(monkeypatch)` (10)
  - `async def find(session_factory, key)` (3)

### `tests/test_schema.py` — 59 строк

Поведение схемы БД: значения по умолчанию, ограничения, порядок outbox.

Зависит от: `app.db`, `app.models`, `tests.helpers`

Тестов: 5


## Абстракции с одной реализацией

Нет.
