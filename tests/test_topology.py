"""Тесты топологии RabbitMQ: TTL и dead-letter очередей повторов."""

import pytest

from app.topology import _retry_queue


@pytest.mark.parametrize(
    ("attempt", "base_delay", "ttl"),
    [(1, 2.0, 2000), (2, 2.0, 4000), (2, 0.5, 1000)],
)
def test_retry_queue_ttl_doubles_with_each_attempt(attempt, base_delay, ttl):
    queue = _retry_queue(attempt, base_delay)

    assert queue.arguments["x-message-ttl"] == ttl


def test_retry_queue_dead_letters_back_to_new_payments():
    arguments = _retry_queue(1, 2.0).arguments

    assert arguments["x-dead-letter-exchange"] == "payments"
    assert arguments["x-dead-letter-routing-key"] == "payments.new"
