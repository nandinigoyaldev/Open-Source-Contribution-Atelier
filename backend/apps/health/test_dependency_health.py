"""
Tests for the dependency checks behind /health/ and /health/ready/.

The views are called through RequestFactory and every dependency is mocked, so
these tests need no database, Redis, Meilisearch or Celery worker.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import requests
from django.test import RequestFactory

from apps.health import views
from apps.health.views import HealthChecker


def _ok(name):
    return {"name": name, "status": "healthy", "details": {}}


def _down(name):
    return {"name": name, "status": "unhealthy", "details": {"error": "boom"}}


def _patch_checks(**overrides):
    """Patch every check on HealthChecker; overrides are results by attribute."""
    results = {
        "check_postgres": _ok("PostgreSQL"),
        "check_redis": _ok("Redis"),
        "check_celery": _ok("Celery Worker"),
        "check_websocket": _ok("WebSocket"),
        "check_meilisearch": _ok("Meilisearch"),
        "check_notification_delivery": _ok("Notification Delivery"),
    }
    results.update(overrides)

    return [
        patch.object(HealthChecker, attr, new=AsyncMock(return_value=value))
        for attr, value in results.items()
    ]


class _Patched:
    def __init__(self, **overrides):
        self.patches = _patch_checks(**overrides)

    def __enter__(self):
        for p in self.patches:
            p.start()

    def __exit__(self, *exc):
        for p in self.patches:
            p.stop()


# --- check_meilisearch -----------------------------------------------------


@pytest.mark.asyncio
async def test_meilisearch_healthy(settings):
    settings.MEILI_URL = "http://meili:7700/"
    response = MagicMock(status_code=200)

    with patch("apps.health.views.requests.get", return_value=response) as get:
        res = await HealthChecker().check_meilisearch()

    assert res["name"] == "Meilisearch"
    assert res["status"] == "healthy"
    get.assert_called_once_with("http://meili:7700/health", timeout=2)


@pytest.mark.asyncio
async def test_meilisearch_unreachable_is_unhealthy(settings):
    settings.MEILI_URL = "http://meili:7700"

    with patch(
        "apps.health.views.requests.get",
        side_effect=requests.ConnectionError("refused"),
    ):
        res = await HealthChecker().check_meilisearch()

    assert res["status"] == "unhealthy"
    assert "refused" in res["details"]["error"]


@pytest.mark.asyncio
async def test_meilisearch_timeout_is_unhealthy(settings):
    settings.MEILI_URL = "http://meili:7700"

    with patch("apps.health.views.requests.get", side_effect=requests.Timeout("slow")):
        res = await HealthChecker().check_meilisearch()

    assert res["status"] == "unhealthy"


@pytest.mark.asyncio
async def test_meilisearch_non_200_is_unhealthy(settings):
    settings.MEILI_URL = "http://meili:7700"

    with patch(
        "apps.health.views.requests.get", return_value=MagicMock(status_code=503)
    ):
        res = await HealthChecker().check_meilisearch()

    assert res["status"] == "unhealthy"
    assert "503" in res["details"]["error"]


@pytest.mark.asyncio
async def test_meilisearch_not_configured_makes_no_request(settings):
    settings.MEILI_URL = ""

    with patch("apps.health.views.requests.get") as get:
        res = await HealthChecker().check_meilisearch()

    assert res["status"] == "not_configured"
    get.assert_not_called()


# --- overall status --------------------------------------------------------


@pytest.mark.asyncio
async def test_all_healthy():
    with _Patched():
        result = await HealthChecker().run_checks()

    assert result["status"] == "healthy"
    assert result["total_checks"] == 6
    assert result["unhealthy_checks"] == 0


@pytest.mark.asyncio
async def test_not_configured_does_not_degrade():
    with _Patched(
        check_meilisearch={
            "name": "Meilisearch",
            "status": "not_configured",
            "details": {},
        }
    ):
        result = await HealthChecker().run_checks()

    assert result["status"] == "healthy"
    assert result["unhealthy_checks"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "check", ["check_celery", "check_websocket", "check_meilisearch"]
)
async def test_optional_dependency_down_is_degraded(check):
    names = {
        "check_celery": "Celery Worker",
        "check_websocket": "WebSocket",
        "check_meilisearch": "Meilisearch",
    }
    with _Patched(**{check: _down(names[check])}):
        result = await HealthChecker().run_checks()

    assert result["status"] == "degraded"
    assert result["unhealthy_checks"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "check,name",
    [("check_postgres", "PostgreSQL"), ("check_redis", "Redis")],
)
async def test_required_dependency_down_is_unhealthy(check, name):
    with _Patched(**{check: _down(name)}):
        result = await HealthChecker().run_checks()

    assert result["status"] == "unhealthy"


@pytest.mark.asyncio
async def test_a_check_that_raises_is_reported_by_name():
    async def explode(self):
        raise RuntimeError("kaput")

    with _Patched(), patch.object(HealthChecker, "check_meilisearch", explode):
        result = await HealthChecker().run_checks()

    assert result["checks"]["Meilisearch"]["status"] == "unhealthy"
    assert result["checks"]["Meilisearch"]["details"]["error"] == "kaput"
    assert result["status"] == "degraded"


# --- views -----------------------------------------------------------------


def _get(view, path):
    return view(RequestFactory().get(path))


def test_health_returns_503_when_database_is_down():
    with _Patched(check_postgres=_down("PostgreSQL")):
        response = _get(views.health_view, "/health/")

    body = json.loads(response.content)
    assert response.status_code == 503
    assert body["status"] == "unhealthy"
    # Each component is listed so monitoring can see which one is down.
    assert body["checks"]["PostgreSQL"]["status"] == "unhealthy"
    assert body["checks"]["Redis"]["status"] == "healthy"
    assert body["checks"]["Meilisearch"]["status"] == "healthy"


def test_health_returns_200_when_only_meilisearch_is_down():
    with _Patched(check_meilisearch=_down("Meilisearch")):
        response = _get(views.health_view, "/health/")

    body = json.loads(response.content)
    assert response.status_code == 200
    assert body["status"] == "degraded"
    assert body["checks"]["Meilisearch"]["status"] == "unhealthy"


def test_health_hides_error_details_from_anonymous_callers():
    with _Patched(check_meilisearch=_down("Meilisearch")):
        response = _get(views.health_view, "/health/")

    body = json.loads(response.content)
    assert "details" not in body["checks"]["Meilisearch"]


def test_ready_is_503_when_redis_is_down():
    with _Patched(check_redis=_down("Redis")):
        response = _get(views.health_ready_view, "/health/ready/")

    assert response.status_code == 503
    assert json.loads(response.content)["status"] == "not_ready"


def test_ready_survives_a_missing_celery_worker():
    with _Patched(check_celery=_down("Celery Worker")):
        response = _get(views.health_ready_view, "/health/ready/")

    assert response.status_code == 200
    assert json.loads(response.content) == {"status": "ready"}
