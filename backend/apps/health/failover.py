"""
Failover status for the dependencies realtime and background work rely on.

Every dependency is reported as one of three states, so an operator or a load
balancer can tell "slow but serving" from "down":

* ``ready``: working normally.
* ``degraded``: still serving, but on a fallback or with a backlog (realtime on the
  in-process channel layer, jobs piling up or stuck).
* ``unavailable``: not working.

The overall state is ``unavailable`` only when a *critical* dependency is
unavailable (``FAILOVER_CRITICAL_DEPENDENCIES``, the database by default), because
that is the one case where taking the instance out of rotation is right. Anything
else being down makes the overall state ``degraded`` and the instance keeps
serving. See docs/DISASTER_RECOVERY.md.

None of the checks put hostnames, credentials or exception text in the result, so the
endpoint is safe to leave open to load balancer probes.
"""

from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any, Callable

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.utils import timezone

logger = logging.getLogger(__name__)

READY = "ready"
DEGRADED = "degraded"
UNAVAILABLE = "unavailable"

# Order matters: the overall state is the worst one that applies.
_SEVERITY = {READY: 0, DEGRADED: 1, UNAVAILABLE: 2}

# Recovery objectives the failure drill checks against (seconds). These are the
# numbers the runbook promises; change them there and here together.
RECOVERY_OBJECTIVES = {
    # A dead worker's run is marked STUCK within its lease (plus one reaper pass),
    # and an eligible run is queued again in that same pass.
    "worker_reap_interval_seconds": 60,
    # Realtime keeps serving on the in-process layer from the first failed call.
    "realtime_switch_seconds": 0,
    # After Redis is back, a process with no subscribers fails back within one probe.
    "realtime_failback_probe_seconds": 15,
}


def _setting(name: str, default):
    return getattr(settings, name, default)


def critical_dependencies() -> set[str]:
    raw = _setting("FAILOVER_CRITICAL_DEPENDENCIES", ("database",))
    if isinstance(raw, str):
        raw = raw.split(",")
    return {item.strip() for item in raw if item and item.strip()}


def worst(states) -> str:
    return max(states, key=lambda s: _SEVERITY[s], default=READY)


def check_database() -> dict[str, Any]:
    start = time.monotonic()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:
        logger.error("Failover database check failed: %s", type(exc).__name__)
        return {"state": UNAVAILABLE, "error": type(exc).__name__}
    return {"state": READY, "latency_ms": round((time.monotonic() - start) * 1000, 1)}


def check_cache() -> dict[str, Any]:
    """Round trip through the default cache (Redis when it is configured)."""
    start = time.monotonic()
    key = "failover:probe"
    try:
        cache.set(key, "1", timeout=5)
        ok = cache.get(key) == "1"
    except Exception as exc:
        logger.error("Failover cache check failed: %s", type(exc).__name__)
        return {"state": UNAVAILABLE, "error": type(exc).__name__}
    if not ok:
        return {"state": UNAVAILABLE, "error": "round trip failed"}
    return {"state": READY, "latency_ms": round((time.monotonic() - start) * 1000, 1)}


def check_realtime() -> dict[str, Any]:
    """
    State of the channel layer behind websockets.

    A ResilientChannelLayer that has switched to its in-memory fallback is
    ``degraded``: connections work but only inside this process. The check also
    gives the layer a chance to fail back when Redis has returned.
    """
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    from apps.core.resilient_channel_layer import ResilientChannelLayer

    try:
        layer = get_channel_layer()
    except Exception as exc:
        logger.error("Failover realtime check failed: %s", type(exc).__name__)
        return {"state": UNAVAILABLE, "error": type(exc).__name__}
    if layer is None:
        return {"state": UNAVAILABLE, "error": "no channel layer configured"}

    if isinstance(layer, ResilientChannelLayer):
        try:
            async_to_sync(layer.try_failback)()
        except Exception:
            logger.debug("Failback probe raised", exc_info=True)
        result = layer.status()
        if result["state"] == DEGRADED:
            if result.get("primary_recovered"):
                result["action"] = (
                    "Redis is back; recycle this realtime worker so clients reconnect "
                    "and the layer fails back."
                )
            else:
                result["action"] = "Realtime fan-out is limited to this process."
        return result

    # A plain in-memory layer. Degraded only when Redis was configured and
    # startup detection could not reach it.
    backend = str(_setting("CHANNEL_LAYER_BACKEND", ""))
    if backend == "inmemory:unavailable":
        return {
            "state": DEGRADED,
            "backend": type(layer).__name__,
            "action": "Redis was unreachable at startup; realtime is single process.",
        }
    return {"state": READY, "backend": type(layer).__name__}


def check_workers() -> dict[str, Any]:
    """
    Background work, judged from the TaskRun table the workers already write:
    how long the oldest queued run has waited, and how many runs lost their worker.
    """
    from apps.monitoring.models import TaskRun

    degraded_age = int(_setting("FAILOVER_QUEUE_AGE_DEGRADED_SECONDS", 300))
    unavailable_age = int(_setting("FAILOVER_QUEUE_AGE_UNAVAILABLE_SECONDS", 1800))
    now = timezone.now()
    try:
        oldest = (
            TaskRun.objects.filter(status="PENDING", queued_at__isnull=False)
            .order_by("queued_at")
            .values_list("queued_at", flat=True)
            .first()
        )
        stuck = TaskRun.objects.filter(status="STUCK").count()
        # Leases that ran out but the reaper has not marked yet.
        expired = TaskRun.objects.filter(
            status="STARTED", lease_expires_at__lt=now
        ).count()
    except Exception as exc:
        logger.error("Failover worker check failed: %s", type(exc).__name__)
        return {"state": UNAVAILABLE, "error": type(exc).__name__}

    age = round((now - oldest).total_seconds(), 1) if oldest else 0.0
    state = READY
    if stuck or expired or age >= degraded_age:
        state = DEGRADED
    if age >= unavailable_age:
        state = UNAVAILABLE
    return {
        "state": state,
        "oldest_queued_age_seconds": age,
        "stuck_runs": stuck,
        "expired_leases": expired,
    }


CHECKS: dict[str, Callable[[], dict[str, Any]]] = {
    "database": check_database,
    "cache": check_cache,
    "realtime": check_realtime,
    "workers": check_workers,
}


def evaluate() -> dict[str, Any]:
    """Run every check and fold them into one overall state."""
    critical = critical_dependencies()
    dependencies: dict[str, dict[str, Any]] = {}
    for name, check in CHECKS.items():
        try:
            dependencies[name] = check()
        except Exception as exc:  # a check must never take the endpoint down
            logger.exception("Failover check %s crashed", name)
            dependencies[name] = {"state": UNAVAILABLE, "error": type(exc).__name__}
        dependencies[name]["critical"] = name in critical

    overall = READY
    for name, result in dependencies.items():
        state = result["state"]
        if state == UNAVAILABLE and name not in critical:
            state = DEGRADED
        overall = worst([overall, state])
    return {
        "status": overall,
        "timestamp": timezone.now().isoformat(),
        "dependencies": dependencies,
    }
