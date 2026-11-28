"""
Health check aggregator endpoint with async verification.
"""

import asyncio
import json
import logging
import time
from datetime import timedelta
from typing import Any, Dict, Optional

import redis
import requests
from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError, connection, connections
from django.db.models import Count
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from redis.backoff import NoBackoff
from redis.exceptions import RedisError
from redis.retry import Retry

logger = logging.getLogger(__name__)

# Postgres and Redis decide whether the app can serve traffic at all. The other
# checks are reported but only mark the overall status "degraded", so a missing
# worker or search index does not take the whole service out of rotation.
REQUIRED_CHECKS = ("PostgreSQL", "Redis")

# Kept short so a hung dependency can never hang the probe.
MEILISEARCH_TIMEOUT_SECONDS = 2

NOTIFICATION_RUNBOOK = "docs/NOTIFICATION_DELIVERY_LEDGER.md#retry-exhaustion-health"


def _check_db_pool() -> dict[str, Any]:
    from apps.core.middleware.db_pool_monitor import (
        fetch_postgres_pool_stats,
        get_conn_max_age,
    )

    max_connections = getattr(settings, "DB_MAX_CONNECTIONS", 97)
    active, idle, total, waiting = fetch_postgres_pool_stats()
    utilization = round((total / max_connections) * 100, 2) if max_connections else 0.0

    status = "healthy"
    if utilization >= 90.0:
        status = "degraded"
    if total >= max_connections:
        status = "unhealthy"

    return {
        "status": status,
        "active": active,
        "idle": idle,
        "total": total,
        "waiting": waiting,
        "max_connections": max_connections,
        "utilization_percent": utilization,
        "conn_max_age": get_conn_max_age(),
    }


def _count_dead_letters(since) -> Dict[str, int]:
    """Dead letters per channel since ``since``. Reads no message content."""
    from apps.notifications.models import NotificationDeadLetter

    try:
        rows = (
            NotificationDeadLetter.objects.filter(failed_at__gte=since)
            .values("channel")
            .annotate(total=Count("id"))
            .order_by("channel")
        )
        return {row["channel"]: row["total"] for row in rows}
    finally:
        # This runs in a short-lived worker thread with its own connection.
        connection.close()


def _has_internal_access(request) -> bool:
    """
    Check whether the requester is allowed to see verbose infrastructure
    details (worker hostnames, Redis stats, ALLOWED_HOSTS value) rather
    than just up/down status. Uses a shared-secret header
    (HEALTH_CHECK_INTERNAL_TOKEN in settings) rather than full user auth,
    since this endpoint is meant to remain usable by unauthenticated
    infra probes (load balancers, Kubernetes) for the minimal status
    check — only the verbose details need gating.
    """
    configured_token = getattr(settings, "HEALTH_CHECK_INTERNAL_TOKEN", None)
    if not configured_token:
        # No token configured: verbose details are never exposed, even
        # internally, until a maintainer explicitly opts in by setting one.
        return False
    provided_token = request.headers.get("X-Health-Check-Token", "")
    return provided_token == configured_token


class HealthChecker:
    """
    Async health checker for all services.
    """

    def __init__(self):
        self.results: Dict[str, Any] = {}
        self.start_time = time.time()

    async def check_postgres(self) -> Dict[str, Any]:
        """Check PostgreSQL connection."""
        result = {
            "name": "PostgreSQL",
            "status": "healthy",
            "details": {},
        }
        try:
            start = time.time()
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            result["details"]["response_time_ms"] = round(
                (time.time() - start) * 1000, 2
            )
            result["details"]["connection_count"] = (
                connection.connection.total_changes()
                if hasattr(connection.connection, "total_changes")
                else "N/A"
            )
        except Exception as e:
            result["status"] = "unhealthy"
            result["details"]["error"] = str(e)
            logger.error(f"PostgreSQL health check failed: {e}")
        return result

    async def check_redis(self) -> Dict[str, Any]:
        """Check Redis connection."""
        result = {
            "name": "Redis",
            "status": "healthy",
            "details": {},
        }
        try:
            start = time.time()
            cache.set("health_check_ping", "pong", timeout=5)
            value = cache.get("health_check_ping")
            if value == "pong":
                result["details"]["response_time_ms"] = round(
                    (time.time() - start) * 1000, 2
                )
                try:
                    redis_client = redis.from_url(settings.REDIS_URL)
                    info = redis_client.info()
                    result["details"]["used_memory_human"] = info.get(
                        "used_memory_human", "N/A"
                    )
                    result["details"]["connected_clients"] = info.get(
                        "connected_clients", "N/A"
                    )
                    result["details"]["uptime_days"] = info.get("uptime_in_days", "N/A")
                except Exception:
                    pass
            else:
                result["status"] = "unhealthy"
                result["details"]["error"] = "Redis ping failed"
        except Exception as e:
            result["status"] = "unhealthy"
            result["details"]["error"] = str(e)
            logger.error(f"Redis health check failed: {e}")
        return result

    async def check_celery(self) -> Dict[str, Any]:
        """Check Celery worker availability."""
        result = {
            "name": "Celery Worker",
            "status": "healthy",
            "details": {},
        }
        try:
            from config.celery import app

            start = time.time()
            i = app.control.inspect()
            if i:
                stats = i.stats()
                if stats:
                    workers = list(stats.keys())
                    result["details"]["active_workers"] = len(workers)
                    result["details"]["workers"] = workers
                    result["details"]["response_time_ms"] = round(
                        (time.time() - start) * 1000, 2
                    )

                    active_queues = i.active_queues()
                    if active_queues:
                        result["details"]["active_queues"] = len(active_queues)
                else:
                    result["status"] = "unhealthy"
                    result["details"]["error"] = "No Celery workers available"
            else:
                result["status"] = "unhealthy"
                result["details"]["error"] = "Celery inspect not available"
        except Exception as e:
            result["status"] = "unhealthy"
            result["details"]["error"] = str(e)
            logger.error(f"Celery health check failed: {e}")
        return result

    async def check_websocket(self) -> Dict[str, Any]:
        """Check WebSocket layer."""
        result = {
            "name": "WebSocket",
            "status": "healthy",
            "details": {},
        }
        try:
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer

            start = time.time()
            channel_layer = get_channel_layer()

            if channel_layer:
                result["details"]["channel_layer_type"] = type(channel_layer).__name__
                result["details"]["response_time_ms"] = round(
                    (time.time() - start) * 1000, 2
                )

                try:
                    group_name = "health_check_group"
                    async_to_sync(channel_layer.group_add)(
                        group_name, "health_check_channel"
                    )
                    result["details"]["group_created"] = True
                except Exception as e:
                    result["details"]["group_error"] = str(e)
            else:
                result["status"] = "unhealthy"
                result["details"]["error"] = "Channel layer not available"
        except Exception as e:
            result["status"] = "unhealthy"
            result["details"]["error"] = str(e)
            logger.error(f"WebSocket health check failed: {e}")
        return result

    async def check_meilisearch(self) -> Dict[str, Any]:
        """Check Meilisearch, if it is configured."""
        result = {
            "name": "Meilisearch",
            "status": "healthy",
            "details": {},
        }
        meili_url = (getattr(settings, "MEILI_URL", "") or "").rstrip("/")
        if not meili_url:
            result["status"] = "not_configured"
            return result

        def _probe() -> int:
            response = requests.get(
                f"{meili_url}/health", timeout=MEILISEARCH_TIMEOUT_SECONDS
            )
            return response.status_code

        try:
            start = time.time()
            status_code = await asyncio.to_thread(_probe)
            result["details"]["response_time_ms"] = round(
                (time.time() - start) * 1000, 2
            )
            if status_code != 200:
                result["status"] = "unhealthy"
                result["details"]["error"] = f"Meilisearch returned HTTP {status_code}"
        except Exception as e:
            result["status"] = "unhealthy"
            result["details"]["error"] = str(e)
            logger.error(f"Meilisearch health check failed: {e}")
        return result

    async def check_notification_delivery(self) -> Dict[str, Any]:
        """Report notifications that recently ran out of delivery attempts."""
        result = {
            "name": "Notification Delivery",
            "status": "healthy",
            "details": {},
        }
        threshold = settings.NOTIFICATION_DEAD_LETTER_HEALTH_THRESHOLD
        if threshold <= 0:
            result["status"] = "not_configured"
            return result

        window = settings.NOTIFICATION_DEAD_LETTER_HEALTH_WINDOW_SECONDS
        try:
            since = timezone.now() - timedelta(seconds=window)
            by_channel = await asyncio.to_thread(_count_dead_letters, since)
            total = sum(by_channel.values())
            result["details"] = {
                "terminal_failures": total,
                "by_channel": by_channel,
                "window_seconds": window,
                "threshold": threshold,
                "runbook": NOTIFICATION_RUNBOOK,
            }
            if total >= threshold:
                result["status"] = "unhealthy"
        except Exception as e:
            result["status"] = "unhealthy"
            result["details"]["error"] = str(e)
            logger.error(f"Notification delivery health check failed: {e}")
        return result

    async def run_checks(self) -> Dict[str, Any]:
        """Run all health checks asynchronously."""
        names = [
            "PostgreSQL",
            "Redis",
            "Celery Worker",
            "WebSocket",
            "Meilisearch",
            "Notification Delivery",
        ]
        tasks = [
            self.check_postgres(),
            self.check_redis(),
            self.check_celery(),
            self.check_websocket(),
            self.check_meilisearch(),
            self.check_notification_delivery(),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.results[names[i]] = {
                    "name": names[i],
                    "status": "unhealthy",
                    "details": {"error": str(result)},
                }
            else:
                self.results[result["name"]] = result

        total_checks = len(self.results)
        healthy_checks = sum(
            1 for r in self.results.values() if r["status"] == "healthy"
        )
        unhealthy_checks = sum(
            1 for r in self.results.values() if r["status"] == "unhealthy"
        )

        required_down = any(
            self.results[name]["status"] != "healthy"
            for name in REQUIRED_CHECKS
            if name in self.results
        )
        if required_down:
            overall_status = "unhealthy"
        elif unhealthy_checks > 0:
            overall_status = "degraded"
        else:
            overall_status = "healthy"

        return {
            "status": overall_status,
            "timestamp": time.time(),
            "total_checks": total_checks,
            "healthy_checks": healthy_checks,
            "unhealthy_checks": unhealthy_checks,
            "checks": self.results,
            "metadata": {
                "version": "1.0.0",
                "environment": getattr(settings, "ENVIRONMENT", "development"),
                "host": getattr(settings, "ALLOWED_HOSTS", ["localhost"])[0],
            },
        }


def _minimal_response(full_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Strip verbose per-service details down to just up/down status, for
    responses to requests without internal access. Keeps the top-level
    overall status intact, since that's what a probe actually needs.
    """
    return {
        "status": full_result["status"],
        "timestamp": full_result["timestamp"],
        "checks": {
            name: {"name": check["name"], "status": check["status"]}
            for name, check in full_result["checks"].items()
        },
    }


@csrf_exempt
@require_http_methods(["GET", "HEAD"])
def health_view(request):
    """
    Health check endpoint.

    GET /health/

    Returns structured health information for all services. Verbose
    per-service details (worker hostnames, Redis stats, ALLOWED_HOSTS)
    are only included for requests with a valid internal access token
    (see _has_internal_access) — unauthenticated requests get minimal
    up/down status only.
    """
    checker = HealthChecker()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(checker.run_checks())
    finally:
        loop.close()

    # "degraded" (an optional dependency is down) still serves traffic.
    status_code = 503 if result["status"] == "unhealthy" else 200

    response_body = (
        result if _has_internal_access(request) else _minimal_response(result)
    )
    return JsonResponse(response_body, status=status_code)


@csrf_exempt
@require_http_methods(["GET", "HEAD"])
def db_health_view(request):
    """
    DB-focused health endpoint used by Render.

    GET /api/health/db/
    """
    result = _check_db_pool()
    status_code = 503 if result["status"] == "unhealthy" else 200
    return JsonResponse(result, status=status_code)


@csrf_exempt
@require_http_methods(["GET"])
def health_ready_view(request):
    """
    Readiness probe endpoint for Kubernetes.

    GET /health/ready/

    Returns 200 if the required services (Postgres, Redis) are up, 503
    otherwise. Optional services only make /health/ report "degraded". Never includes
    verbose infrastructure details, regardless of caller — a readiness
    probe only needs the boolean outcome.
    """
    checker = HealthChecker()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(checker.run_checks())
    finally:
        loop.close()

    if result["status"] != "unhealthy":
        return JsonResponse({"status": "ready"}, status=200)
    else:
        return JsonResponse(
            {"status": "not_ready", "unhealthy": result["unhealthy_checks"]}, status=503
        )


@csrf_exempt
@require_http_methods(["GET"])
def health_live_view(request):
    """
    Liveness probe endpoint for Kubernetes.

    GET /health/live/

    Returns 200 if the application is running.
    """
    return JsonResponse({"status": "alive"}, status=200)


@never_cache
@require_http_methods(["GET"])
def worker_readiness_view(request):
    """Check only the database and configured Django-Q Redis broker."""
    broker = settings.Q_CLUSTER
    dependencies = {"database": "ready", "redis": "not_configured"}

    try:
        with connections[broker.get("orm") or "default"].cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        dependencies["database"] = "unavailable"

    redis_url = broker.get("redis")
    if redis_url:
        try:
            with redis.from_url(
                redis_url,
                socket_connect_timeout=1,
                socket_timeout=1,
                retry=Retry(NoBackoff(), 0),
            ) as client:
                dependencies["redis"] = "ready" if client.ping() else "unavailable"
        except (RedisError, ValueError):
            dependencies["redis"] = "unavailable"

    ready = "unavailable" not in dependencies.values()
    return JsonResponse(
        {
            "status": "ready" if ready else "not_ready",
            "dependencies": dependencies,
        },
        status=200 if ready else 503,
    )


@csrf_exempt
@require_http_methods(["GET"])
def replication_lag_view(request):
    """
    Replication lag monitoring endpoint.

    GET /health/db/replication-lag/

    Returns lag seconds for each configured replica. Responds 200 if all
    replicas are within threshold, 503 if any exceed it or are in error.
    """
    from config.db_router import PrimaryReplicaRouter

    router = PrimaryReplicaRouter()
    lag_info = router.get_replica_lag_info()

    has_error = any(r["status"] in ("error", "lagging") for r in lag_info)
    status_code = 503 if has_error else 200

    payload = {
        "status": "degraded" if has_error else "healthy",
        "replicas": lag_info,
        "threshold_seconds": getattr(settings, "REPLICA_LAG_ALERT_SECONDS", 30),
    }
    return JsonResponse(payload, status=status_code)


@csrf_exempt
@never_cache
@require_http_methods(["GET", "HEAD"])
def failover_status_view(request):
    """
    Tri-state dependency status for failover decisions.

    GET /health/failover/

    Each dependency (database, cache, realtime, workers) is ``ready``, ``degraded``
    or ``unavailable``. HTTP 503 only when a critical dependency is unavailable;
    ``degraded`` still answers 200 so the instance stays in rotation. Carries no
    hostnames or credentials. See docs/DISASTER_RECOVERY.md.
    """
    from apps.health import failover

    result = failover.evaluate()
    return JsonResponse(
        result, status=503 if result["status"] == failover.UNAVAILABLE else 200
    )
