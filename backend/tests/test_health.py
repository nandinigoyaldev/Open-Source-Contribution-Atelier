import json
from unittest.mock import MagicMock, patch

import pytest
from django.test import RequestFactory

from config.health_view import health_view


@pytest.fixture
def request_factory():
    return RequestFactory()


def _payload(response):
    return json.loads(response.content)


class TestHealthEndpoint:
    def test_returns_json_response(self, request_factory):
        with (
            patch("config.health_view._check_postgres", return_value={"status": "ok"}),
            patch("config.health_view._check_redis", return_value={"status": "ok"}),
        ):
            response = health_view(request_factory.get("/health/"))
        assert response.status_code == 200

    def test_response_shape(self, request_factory):
        with (
            patch("config.health_view._check_postgres", return_value={"status": "ok"}),
            patch("config.health_view._check_redis", return_value={"status": "ok"}),
        ):
            response = health_view(request_factory.get("/health/"))
        payload = _payload(response)
        assert "status" in payload
        assert "services" in payload
        assert "postgres" in payload["services"]
        assert "redis" in payload["services"]

    def test_healthy_when_postgres_and_redis_ok(self, request_factory):
        with (
            patch(
                "config.health_view._check_postgres",
                return_value={"status": "ok"},
            ),
            patch(
                "config.health_view._check_redis",
                return_value={"status": "ok"},
            ),
        ):
            response = health_view(request_factory.get("/health/"))

        assert response.status_code == 200
        assert _payload(response)["status"] == "healthy"

    def test_unhealthy_when_postgres_fails(self, request_factory):
        with (
            patch(
                "config.health_view._check_postgres",
                return_value={"status": "error", "detail": "connection refused"},
            ),
            patch(
                "config.health_view._check_redis",
                return_value={"status": "ok"},
            ),
        ):
            response = health_view(request_factory.get("/health/"))

        assert response.status_code == 503
        assert _payload(response)["status"] == "unhealthy"

    def test_unhealthy_when_redis_fails(self, request_factory):
        with (
            patch(
                "config.health_view._check_postgres",
                return_value={"status": "ok"},
            ),
            patch(
                "config.health_view._check_redis",
                return_value={"status": "error", "detail": "connection refused"},
            ),
        ):
            response = health_view(request_factory.get("/health/"))

        assert response.status_code == 503
        assert _payload(response)["status"] == "unhealthy"

    def test_degraded_when_services_not_configured(self, request_factory):
        with (
            patch(
                "config.health_view._check_postgres",
                return_value={
                    "status": "not_configured",
                    "detail": "PostgreSQL is not the active database engine",
                },
            ),
            patch(
                "config.health_view._check_redis",
                return_value={"status": "not_configured", "detail": "REDIS_URL is not set"},
            ),
        ):
            response = health_view(request_factory.get("/health/"))

        assert response.status_code == 200
        assert _payload(response)["status"] == "degraded"


class TestPostgresCheck:
    def test_reports_not_configured_for_non_postgres_engine(self):
        from config.health_view import _check_postgres

        with patch("config.health_view.settings") as mock_settings:
            mock_settings.DATABASES = {
                "default": {"ENGINE": "django.db.backends.sqlite3"}
            }
            result = _check_postgres()

        assert result["status"] == "not_configured"

    def test_reports_ok_when_query_succeeds(self):
        from config.health_view import _check_postgres

        mock_cursor = MagicMock()
        mock_cursor.__enter__.return_value = mock_cursor
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with (
            patch("config.health_view.settings") as mock_settings,
            patch("config.health_view.connections") as mock_connections,
        ):
            mock_settings.DATABASES = {
                "default": {"ENGINE": "django.db.backends.postgresql"}
            }
            mock_connections.__getitem__.return_value = mock_conn
            result = _check_postgres()

        assert result == {"status": "ok"}
        mock_conn.ensure_connection.assert_called_once()
        mock_cursor.execute.assert_called_once_with("SELECT 1")


class TestRedisCheck:
    def test_reports_not_configured_when_url_missing(self):
        from config.health_view import _check_redis

        with (
            patch("config.health_view.os.getenv", return_value=""),
            patch("config.health_view.settings.CELERY_BROKER_URL", ""),
        ):
            result = _check_redis()

        assert result["status"] == "not_configured"

    def test_reports_ok_when_ping_succeeds(self):
        from config.health_view import _check_redis

        mock_client = MagicMock()

        with (
            patch("config.health_view.os.getenv", return_value="redis://127.0.0.1:6379/0"),
            patch("config.health_view.redis.from_url", return_value=mock_client),
        ):
            result = _check_redis()

        assert result == {"status": "ok"}
        mock_client.ping.assert_called_once()
