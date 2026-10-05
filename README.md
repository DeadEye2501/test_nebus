# Сервис процессинга платежей

Принимает платёж, через outbox и RabbitMQ передаёт его consumer'у, эмулирует
платёжный шлюз (2–5 с, 90 % успеха) и сообщает результат webhook'ом.

## Запуск

```bash
docker compose up --build
```

Поднимаются `postgres`, `rabbitmq`, `migrate` (миграции, завершается), `api`
(порт 8000), `relay` (публикация из outbox), `consumer`.

Ключ API, логин и пароль Swagger по умолчанию — в `.env.example`; чтобы
поменять, скопируйте его в `.env` и правьте.

- Swagger: http://localhost:8000/docs — браузер спросит логин и пароль
  (`docs` / `docs-password`); запросы из Swagger — после Authorize с `X-API-Key`.
- RabbitMQ UI: http://localhost:15672 (`guest` / `guest`).

## Примеры

Создать платёж (адрес webhook — свой со https://webhook.site):

```bash
curl -i -X POST http://localhost:8000/api/v1/payments \
  -H "X-API-Key: dev-api-key" -H "Idempotency-Key: order-42" \
  -H "Content-Type: application/json" \
  -d '{"amount": "100.50", "currency": "RUB", "description": "Заказ 42",
       "metadata": {"order_id": 42}, "webhook_url": "https://webhook.site/<ваш-id>"}'
```

Ответ `202` с `payment_id`, `status: pending`, `created_at`. Через 2–5 с на
webhook придёт полное состояние платежа.

Прочитать платёж:

```bash
curl -s http://localhost:8000/api/v1/payments/<payment_id> -H "X-API-Key: dev-api-key"
```

Повтор с тем же `Idempotency-Key` и тем же телом вернёт тот же `payment_id`; с
другим телом — `409`. Без `X-API-Key` или с неверным — `401`.

## Повторы и DLQ

Технический сбой (webhook ответил не 2xx, недоступен, БД недоступна) — сообщение
уходит в `payments.new.retry.1` (2 с), затем в `payments.new.retry.2` (4 с) и
возвращается в `payments.new`; после третьей неудачи — в `payments.new.dlq` с
заголовками `x-attempt` (номер последней попытки) и `x-error` (`Тип: текст`).
Отказ шлюза (10 %) — не сбой: статус `failed`, webhook уходит, повторов нет.

Посмотреть DLQ: создайте платёж с `"webhook_url": "http://localhost:9/hook"`
(внутри контейнера там никто не слушает). Через ~8–11 с (эмуляция 2–5 с плюс
задержки 2 и 4 с) сообщение появится в `payments.new.dlq` в RabbitMQ UI.

## Гарантии

- Платёж и событие пишутся в одной транзакции (outbox); relay публикует события
  с подтверждением брокера и отмечает их; `FOR UPDATE SKIP LOCKED` позволяет
  запускать несколько relay.
- Доставка at-least-once: consumer идемпотентен — статус пишется условным
  апдейтом, повтор шлюз не вызывает, а только переотправляет webhook. Дубли
  webhook различимы по `payment_id`.

## Тесты

Нужен PostgreSQL с базой `payments_test` (RabbitMQ тестам не нужен — брокер
подменяется `TestRabbitBroker`). Строку подключения положите в `.env`:

```
DATABASE_URL=postgresql+asyncpg://<user>:<password>@localhost:5432/payments_test
```

```bash
pipenv install --dev
pipenv run pytest
```

Тесты пересоздают схему `public` в `payments_test` — не указывайте рабочую базу.
