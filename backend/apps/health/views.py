"""
Health check aggregator endpoint with async verification.
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional
from django.db import connection
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
import redis
import json

logger = logging.getLogger(__name__)


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
            # Try to ping Redis
            cache.set("health_check_ping", "pong", timeout=5)
            value = cache.get("health_check_ping")
            if value == "pong":
                result["details"]["response_time_ms"] = round(
                    (time.time() - start) * 1000, 2
                )
                # Get Redis info
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
                except:
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
            from celery.task.control import inspect
            from config.celery import app

            start = time.time()
            i = inspect(app)
            if i:
                stats = i.stats()
                if stats:
                    workers = list(stats.keys())
                    result["details"]["active_workers"] = len(workers)
                    result["details"]["workers"] = workers
                    result["details"]["response_time_ms"] = round(
                        (time.time() - start) * 1000, 2
                    )

                    # Get queue sizes
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
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync

            start = time.time()
            channel_layer = get_channel_layer()

            # Check if channel layer is configured
            if channel_layer:
                result["details"]["channel_layer_type"] = type(channel_layer).__name__
                result["details"]["response_time_ms"] = round(
                    (time.time() - start) * 1000, 2
                )

                # Try to create a test group
                try:
                    group_name = "health_check_group"
                    async_to_sync(channel_layer.group_add)(
                        group_name, "health_check_channel"
                    )
                    result["details"]["group_created"] = True
                except Exception as e:
                    result["details"]["group_error"] = str(e)
                    # Don't fail if group creation fails (may be permissions)
            else:
                result["status"] = "unhealthy"
                result["details"]["error"] = "Channel layer not available"
        except Exception as e:
            result["status"] = "unhealthy"
            result["details"]["error"] = str(e)
            logger.error(f"WebSocket health check failed: {e}")
        return result

    async def run_checks(self) -> Dict[str, Any]:
        """Run all health checks asynchronously."""
        # Run checks in parallel
        tasks = [
            self.check_postgres(),
            self.check_redis(),
            self.check_celery(),
            self.check_websocket(),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                names = ["PostgreSQL", "Redis", "Celery Worker", "WebSocket"]
                self.results[names[i]] = {
                    "name": names[i],
                    "status": "unhealthy",
                    "details": {"error": str(result)},
                }
            else:
                self.results[result["name"]] = result

        # Calculate overall status
        total_checks = len(self.results)
        healthy_checks = sum(
            1 for r in self.results.values() if r["status"] == "healthy"
        )
        unhealthy_checks = total_checks - healthy_checks

        overall_status = "healthy" if unhealthy_checks == 0 else "unhealthy"

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


@csrf_exempt
@require_http_methods(["GET", "HEAD"])
def health_view(request):
    """
    Health check endpoint.

    GET /health/

    Returns structured health information for all services.
    """
    checker = HealthChecker()

    # Run checks synchronously (Django doesn't support async views out of the box)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(checker.run_checks())
    finally:
        loop.close()

    # Determine HTTP status code
    status_code = 200 if result["status"] == "healthy" else 503

    return JsonResponse(result, status=status_code)


@csrf_exempt
@require_http_methods(["GET"])
def health_ready_view(request):
    """
    Readiness probe endpoint for Kubernetes.

    GET /health/ready/

    Returns 200 if all services are ready, 503 otherwise.
    """
    checker = HealthChecker()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(checker.run_checks())
    finally:
        loop.close()

    if result["status"] == "healthy":
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
