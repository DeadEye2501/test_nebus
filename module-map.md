# Карта модулей

Собирается из кода, а не ведётся руками.
Править руками нельзя — правки затрёт следующая сборка.
Число в скобках — сколько строк занимает объявление.

## app — 3 модулей

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

## tests — 3 модулей

### `tests/conftest.py` — 53 строк

Общие фикстуры: схема тестовой БД из миграций и чистые таблицы перед каждым тестом.

Зависит от: `app.config`, `app.db`

- `def pytest_collection_modifyitems(items: list[pytest.Item]) -> None` (7)
- `async def _schema()` (11)
- `async def _clean_tables(_schema)` (3)
- `def session_factory()` (2)
- `async def session(session_factory)` (3)

### `tests/helpers.py` — 20 строк

Построители тестовых данных.

Зависит от: `app.models`

- `def payment_row(**overrides) -> Payment` (12)

### `tests/test_schema.py` — 59 строк

Поведение схемы БД: значения по умолчанию, ограничения, порядок outbox.

Зависит от: `app.db`, `app.models`, `tests.helpers`

Тестов: 5


## Абстракции с одной реализацией

Нет.
