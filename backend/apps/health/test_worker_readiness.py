import json
from unittest.mock import ANY, MagicMock

import pytest
from django.db import OperationalError
from django.urls import resolve
from redis.exceptions import ConnectionError

from . import views

WORKER_READY_PATH = "/health/worker-ready/"


@pytest.mark.parametrize(
    ("database_ready", "redis_ready", "status_code"),
    [(True, True, 200), (False, True, 503), (True, False, 503), (False, False, 503)],
)
def test_worker_readiness_checks_only_required_dependencies(
    rf, settings, monkeypatch, database_ready, redis_ready, status_code
):
    redis_url = "redis://example.invalid:6379/2"
    settings.Q_CLUSTER = {"redis": redis_url}
    databases = MagicMock()
    configure_redis = MagicMock()
    monkeypatch.setattr(views, "connections", databases)
    monkeypatch.setattr(views.redis, "from_url", configure_redis)
    database = databases["default"]
    cursor = database.cursor.return_value.__enter__.return_value
    client = configure_redis.return_value.__enter__.return_value
    client.ping.return_value = True
    if not database_ready:
        cursor.execute.side_effect = OperationalError("database connection details")
    if not redis_ready:
        client.ping.side_effect = ConnectionError("Redis connection details")

    response = resolve(WORKER_READY_PATH).func(rf.get(WORKER_READY_PATH))

    assert response.status_code == status_code
    assert json.loads(response.content) == {
        "status": "ready" if status_code == 200 else "not_ready",
        "dependencies": {
            "database": "ready" if database_ready else "unavailable",
            "redis": "ready" if redis_ready else "unavailable",
        },
    }
    assert "no-store" in response.headers["Cache-Control"]
    cursor.execute.assert_called_once_with("SELECT 1")
    configure_redis.assert_called_once_with(
        redis_url, socket_connect_timeout=1, socket_timeout=1, retry=ANY
    )
    assert configure_redis.call_args.kwargs["retry"].get_retries() == 0
    client.ping.assert_called_once_with()
    client.info.assert_not_called()


def test_worker_readiness_skips_redis_for_the_orm_broker(rf, settings, monkeypatch):
    settings.Q_CLUSTER = {"orm": "replica"}
    databases = MagicMock()
    configure_redis = MagicMock()
    monkeypatch.setattr(views, "connections", databases)
    monkeypatch.setattr(views.redis, "from_url", configure_redis)

    response = resolve(WORKER_READY_PATH).func(rf.get(WORKER_READY_PATH))

    assert response.status_code == 200
    assert json.loads(response.content) == {
        "status": "ready",
        "dependencies": {"database": "ready", "redis": "not_configured"},
    }
    databases.__getitem__.assert_called_with("replica")
    configure_redis.assert_not_called()
