# Карта данных

Собирается из кода, а не ведётся руками.
Править руками нельзя — правки затрёт следующая сборка.
У набора называется размер, а не содержимое.

## app

### `app/config.py`

- `class Settings(BaseSettings)`
  - `database_url: str`

### `app/models.py`

- `class Currency(enum.StrEnum)`
  - `RUB` = `'RUB'`
  - `USD` = `'USD'`
  - `EUR` = `'EUR'`
- `class PaymentStatus(enum.StrEnum)`
  - `PENDING` = `'pending'`
  - `SUCCEEDED` = `'succeeded'`
  - `FAILED` = `'failed'`
- `class Payment(Base)`
  - `__tablename__` = `'payments'`
  - `__table_args__` = `набор из 1`
  - `__mapper_args__: ClassVar[dict]` = `словарь из 1`
  - `id: Mapped[uuid.UUID]` = `mapped_column(primary_key=True)`
  - `amount: Mapped[Decimal]` = `mapped_column(Numeric(18, 2))`
  - `currency: Mapped[Currency]` = `mapped_column(_db_enum(Currency, 'currency'))`
  - `description: Mapped[str]` = `mapped_column(String(500))`
  - `meta: Mapped[dict]` = `mapped_column('metadata', JSONB, server_default=…`
  - `status: Mapped[PaymentStatus]` = `mapped_column(_db_enum(PaymentStatus, 'payment_s…`
  - `idempotency_key: Mapped[str]` = `mapped_column(String(255), unique=True)`
  - `request_hash: Mapped[str]` = `mapped_column(CHAR(64))`
  - `webhook_url: Mapped[str]` = `mapped_column(String(2048))`
  - `created_at: Mapped[datetime]` = `mapped_column(DateTime(timezone=True), server_de…`
  - `processed_at: Mapped[datetime | None]` = `mapped_column(DateTime(timezone=True))`
- `class OutboxEvent(Base)`
  - `__tablename__` = `'outbox'`
  - `__table_args__` = `набор из 1`
  - `__mapper_args__: ClassVar[dict]` = `словарь из 1`
  - `id: Mapped[int]` = `mapped_column(BigInteger, Identity(), primary_ke…`
  - `payload: Mapped[dict]` = `mapped_column(JSONB)`
  - `created_at: Mapped[datetime]` = `mapped_column(DateTime(timezone=True), server_de…`
  - `published_at: Mapped[datetime | None]` = `mapped_column(DateTime(timezone=True))`

### `app/payments.py`

- `Sessions` = `async_sessionmaker[AsyncSession]`

### `app/schemas.py`

- `CENT` = `Decimal('0.01')`
- `WebhookUrl` = `Annotated[AnyUrl, UrlConstraints(max_length=2048…`
- `PaymentId` = `Annotated[uuid.UUID, Field(validation_alias=Alia…`
- `Metadata` = `Annotated[dict[str, Any], Field(validation_alias…`
- `class PaymentCreate(BaseModel)`
  - `amount: Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=2)]`
  - `currency: Currency`
  - `description: Annotated[str, Field(min_length=1, max_length=500)]`
  - `metadata: dict[str, Any]` = `Field(default_factory=dict)`
  - `webhook_url: WebhookUrl`
- `class PaymentAccepted(BaseModel)`
  - `model_config` = `ConfigDict(from_attributes=True)`
  - `payment_id: PaymentId`
  - `status: PaymentStatus`
  - `created_at: datetime`
- `class PaymentDetail(BaseModel)`
  - `model_config` = `ConfigDict(from_attributes=True)`
  - `payment_id: PaymentId`
  - `amount: Decimal`
  - `currency: Currency`
  - `description: str`
  - `metadata: Metadata`
  - `status: PaymentStatus`
  - `idempotency_key: str`
  - `webhook_url: str`
  - `created_at: datetime`
  - `processed_at: datetime | None`
- `class NewPaymentEvent(BaseModel)`
  - `payment_id: uuid.UUID`

## migrations

### `migrations/versions/0001_payments_and_outbox.py`

- `revision` = `'0001'`
- `down_revision` = `None`
