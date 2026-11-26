"""
Custom Prometheus collectors for Celery and Redis monitoring.

Tracks:
- Redis queue length per priority queue (celery, default, high_priority, low_priority)
- Unacknowledged in-flight task counts
- Worker task execution duration percentiles (P50, P95, P99)
- Active worker counts and heartbeat status
"""

from __future__ import annotations

import logging
import math
import os
from collections import defaultdict
from typing import Any, Iterable

from django.conf import settings

logger = logging.getLogger(__name__)

_PROMETHEUS_AVAILABLE = False
try:
    from prometheus_client import REGISTRY
    from prometheus_client.core import GaugeMetricFamily

    _PROMETHEUS_AVAILABLE = True
except ImportError:
    REGISTRY = None
    GaugeMetricFamily = None


PRIORITY_QUEUES = ("celery", "default", "high_priority", "low_priority")


def get_redis_queue_lengths(queues: Iterable[str] = PRIORITY_QUEUES) -> dict[str, int]:
    """Inspect Redis broker to get current queue depths per priority queue."""
    lengths = {q: 0 for q in queues}
    broker_url = os.getenv(
        "CELERY_BROKER_URL",
        getattr(settings, "CELERY_BROKER_URL", "redis://localhost:6379/0"),
    )
    if broker_url and broker_url.startswith("redis"):
        try:
            import redis

            r = redis.Redis.from_url(broker_url, socket_timeout=1.0)
            for q in queues:
                try:
                    lengths[q] = r.llen(q)
                except Exception:
                    pass
        except Exception as exc:
            logger.debug("Failed to connect to Redis to get queue lengths: %s", exc)
    return lengths


def get_unacknowledged_task_count() -> int:
    """
    Count unacknowledged tasks across Redis kombu unacked key, Celery worker reserved tasks,
    and fallback to database TaskRun records.
    """
    # 1. Try Redis unacked zset (standard Kombu Redis broker storage)
    broker_url = os.getenv(
        "CELERY_BROKER_URL",
        getattr(settings, "CELERY_BROKER_URL", "redis://localhost:6379/0"),
    )
    if broker_url and broker_url.startswith("redis"):
        try:
            import redis

            r = redis.Redis.from_url(broker_url, socket_timeout=1.0)
            unacked = r.zcard("unacked")
            if unacked is not None and unacked > 0:
                return int(unacked)
        except Exception:
            pass

    # 2. Try Celery worker inspect reserved
    try:
        from celery import current_app

        inspect = current_app.control.inspect(timeout=0.5)
        reserved = inspect.reserved()
        if reserved:
            return sum(len(tasks) for tasks in reserved.values())
    except Exception:
        pass

    # 3. Fallback to active TaskRun model in DB
    try:
        from apps.monitoring.models import TaskRun

        return TaskRun.objects.filter(status="STARTED").count()
    except Exception:
        return 0


def calculate_percentiles(samples: list[float]) -> dict[str, float]:
    """Calculate P50, P95, and P99 percentiles from a list of durations."""
    if not samples:
        return {"0.5": 0.0, "0.95": 0.0, "0.99": 0.0}

    sorted_samples = sorted(samples)
    n = len(sorted_samples)

    def _p(p: float) -> float:
        k = (n - 1) * p
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return round(sorted_samples[int(k)], 4)
        val = sorted_samples[int(f)] * (c - k) + sorted_samples[int(c)] * (k - f)
        return round(val, 4)

    return {
        "0.5": _p(0.50),
        "0.95": _p(0.95),
        "0.99": _p(0.99),
    }


def get_task_duration_percentiles() -> (
    tuple[dict[str, float], dict[str, dict[str, float]]]
):
    """
    Retrieve task execution durations from TaskRun and compute P50, P95, P99.
    Returns: (overall_percentiles, per_task_percentiles)
    """
    durations_by_task: dict[str, list[float]] = defaultdict(list)
    all_durations: list[float] = []

    try:
        from apps.monitoring.models import TaskRun

        runs = (
            TaskRun.objects.filter(status="SUCCESS", duration__isnull=False)
            .order_by("-finished_at")[:1000]
            .values_list("task_name", "duration")
        )
        for task_name, dur in runs:
            if dur is not None and dur >= 0:
                durations_by_task[task_name].append(float(dur))
                all_durations.append(float(dur))
    except Exception as exc:
        logger.debug("Failed to query TaskRun durations: %s", exc)

    overall = calculate_percentiles(all_durations)
    per_task = {t: calculate_percentiles(d) for t, d in durations_by_task.items()}
    return overall, per_task


def get_active_workers_info() -> tuple[int, str]:
    """Return count of active workers and overall heartbeat status ('healthy' or 'down')."""
    try:
        from apps.monitoring.celery_monitor import get_celery_stats

        stats = get_celery_stats()
        worker_count = stats.get("worker_count", 0)
        heartbeat = stats.get("worker_heartbeat", {})
        status_str = heartbeat.get("status", "down" if worker_count == 0 else "healthy")
        return worker_count, status_str
    except Exception:
        return 0, "down"


class CeleryMetricsCollector:
    """
    Prometheus custom collector yielding:
    - celery_queue_length (per priority queue)
    - celery_unacknowledged_tasks
    - celery_task_execution_duration_seconds (P50, P95, P99 percentiles)
    - celery_active_workers
    - celery_worker_heartbeat_status
    """

    def collect(self):
        if not _PROMETHEUS_AVAILABLE or GaugeMetricFamily is None:
            return

        # 1. Redis queue length per priority queue
        queue_lengths = get_redis_queue_lengths()
        queue_metric = GaugeMetricFamily(
            "celery_queue_length",
            "Redis queue length per priority queue",
            labels=["queue"],
        )
        queue_size_metric = GaugeMetricFamily(
            "celery_queue_size",
            "Size of Celery queues (alias)",
            labels=["queue_name"],
        )
        for q, length in queue_lengths.items():
            queue_metric.add_metric([q], float(length))
            queue_size_metric.add_metric([q], float(length))
        yield queue_metric
        yield queue_size_metric

        # 2. Unacknowledged task count
        unacked_count = get_unacknowledged_task_count()
        unacked_metric = GaugeMetricFamily(
            "celery_unacknowledged_tasks",
            "Count of unacknowledged Celery tasks currently in-flight",
        )
        unacked_metric.add_metric([], float(unacked_count))
        yield unacked_metric

        # 3. Worker task execution duration percentiles (P50, P95, P99)
        overall_p, per_task_p = get_task_duration_percentiles()
        duration_metric = GaugeMetricFamily(
            "celery_task_execution_duration_seconds",
            "Worker task execution duration percentiles (P50, P95, P99)",
            labels=["task_name", "quantile"],
        )
        for q in ("0.5", "0.95", "0.99"):
            duration_metric.add_metric(["all", q], overall_p[q])

        for task_name, p_dict in per_task_p.items():
            for q in ("0.5", "0.95", "0.99"):
                duration_metric.add_metric([task_name, q], p_dict[q])
        yield duration_metric

        # 4. Active worker count & heartbeat status
        worker_count, heartbeat_status = get_active_workers_info()
        workers_metric = GaugeMetricFamily(
            "celery_active_workers",
            "Number of active Celery workers responding to heartbeat/ping",
        )
        workers_metric.add_metric([], float(worker_count))
        yield workers_metric

        heartbeat_metric = GaugeMetricFamily(
            "celery_worker_heartbeat_status",
            "Celery worker heartbeat health status (1 = healthy, 0 = down/degraded)",
            labels=["status"],
        )
        heartbeat_metric.add_metric(
            [heartbeat_status], 1.0 if heartbeat_status == "healthy" else 0.0
        )
        yield heartbeat_metric

    def render_prometheus_text(self) -> str:
        """Render Prometheus exposition text for in-memory / fallback metrics scraper."""
        lines: list[str] = []

        # 1. Queue lengths
        queue_lengths = get_redis_queue_lengths()
        lines.append("# HELP celery_queue_length Redis queue length per priority queue")
        lines.append("# TYPE celery_queue_length gauge")
        for q, length in sorted(queue_lengths.items()):
            lines.append(f'celery_queue_length{{queue="{q}"}} {length}')

        # 2. Unacknowledged tasks
        unacked = get_unacknowledged_task_count()
        lines.append(
            "# HELP celery_unacknowledged_tasks Count of unacknowledged Celery tasks currently in-flight"
        )
        lines.append("# TYPE celery_unacknowledged_tasks gauge")
        lines.append(f"celery_unacknowledged_tasks {unacked}")

        # 3. Percentiles
        overall_p, per_task_p = get_task_duration_percentiles()
        lines.append(
            "# HELP celery_task_execution_duration_seconds Worker task execution duration percentiles (P50, P95, P99)"
        )
        lines.append("# TYPE celery_task_execution_duration_seconds gauge")
        for q in ("0.5", "0.95", "0.99"):
            lines.append(
                f'celery_task_execution_duration_seconds{{quantile="{q}",task_name="all"}} {overall_p[q]}'
            )
        for task_name, p_dict in sorted(per_task_p.items()):
            for q in ("0.5", "0.95", "0.99"):
                lines.append(
                    f'celery_task_execution_duration_seconds{{quantile="{q}",task_name="{task_name}"}} {p_dict[q]}'
                )

        # 4. Workers
        worker_count, heartbeat_status = get_active_workers_info()
        lines.append(
            "# HELP celery_active_workers Number of active Celery workers responding to heartbeat/ping"
        )
        lines.append("# TYPE celery_active_workers gauge")
        lines.append(f"celery_active_workers {worker_count}")

        lines.append(
            "# HELP celery_worker_heartbeat_status Celery worker heartbeat health status"
        )
        lines.append("# TYPE celery_worker_heartbeat_status gauge")
        lines.append(
            f'celery_worker_heartbeat_status{{status="{heartbeat_status}"}} {1.0 if heartbeat_status == "healthy" else 0.0}'
        )

        return "\n".join(lines) + "\n"


_collector_instance: CeleryMetricsCollector | None = None
_registered = False


def register_collectors() -> CeleryMetricsCollector:
    """Register CeleryMetricsCollector with the default Prometheus registry."""
    global _collector_instance, _registered
    if _collector_instance is None:
        _collector_instance = CeleryMetricsCollector()

    if _PROMETHEUS_AVAILABLE and REGISTRY is not None and not _registered:
        try:
            REGISTRY.register(_collector_instance)
            _registered = True
        except ValueError:
            # Already registered
            _registered = True
        except Exception as exc:
            logger.debug(
                "Failed to register CeleryMetricsCollector with REGISTRY: %s", exc
            )

    return _collector_instance
