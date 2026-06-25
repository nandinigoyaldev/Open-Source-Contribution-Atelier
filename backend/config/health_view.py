import os
from typing import Any

import redis
from django.conf import settings
from django.db import connections
from django.db.utils import OperationalError
from django.http import JsonResponse, HttpRequest


def _check_postgres() -> dict[str, Any]:
    engine = settings.DATABASES["default"].get("ENGINE", "")
    if "postgresql" not in engine and "postgis" not in engine:
        return {
            "status": "not_configured",
            "detail": "PostgreSQL is not the active database engine",
        }

    try:
        conn = connections["default"]
        conn.ensure_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
        return {"status": "ok"}
    except OperationalError as exc:
        return {"status": "error", "detail": str(exc)}


def _check_redis() -> dict[str, Any]:
    redis_url = os.getenv("REDIS_URL") or getattr(settings, "CELERY_BROKER_URL", "")
    if not redis_url:
        return {"status": "not_configured", "detail": "REDIS_URL is not set"}

    try:
        client = redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
        client.ping()
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


def _overall_status(services: dict[str, dict[str, Any]]) -> tuple[str, int]:
    if any(service["status"] == "error" for service in services.values()):
        return "unhealthy", 503
    if all(service["status"] == "ok" for service in services.values()):
        return "healthy", 200
    return "degraded", 200


def health_view(request: HttpRequest) -> JsonResponse:
    """Returns connection status for PostgreSQL and Redis."""
    services = {
        "postgres": _check_postgres(),
        "redis": _check_redis(),
    }
    overall, status_code = _overall_status(services)
    return JsonResponse(
        {"status": overall, "services": services},
        status=status_code,
    )
