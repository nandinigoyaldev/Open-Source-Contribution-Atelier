import logging
import os
from datetime import timedelta

from celery.signals import task_failure, task_postrun, task_prerun, task_retry
from django.db import models
from django.utils import timezone

from apps.monitoring.models import TaskRun
from apps.monitoring.utils.redaction import format_redacted_args

logger = logging.getLogger(__name__)


def get_celery_stats():
    """
    Exposes Celery metrics: queue depth, worker count, active tasks, reserved tasks.
    Gracefully handles Redis/Broker connection failures.
    """
    stats_data = {
        "worker_count": 0,
        "active_tasks": 0,
        "reserved_tasks": 0,
        "total_queue_depth": 0,
        "queues": {},
    }

    # 1. Attempt worker inspection
    try:
        from celery import current_app

        inspect = current_app.control.inspect(timeout=1.0)

        # Workers & Active tasks
        active = inspect.active()
        if active:
            stats_data["worker_count"] = len(active)
            stats_data["active_tasks"] = sum(len(tasks) for tasks in active.values())

        # Reserved tasks
        reserved = inspect.reserved()
        if reserved:
            stats_data["reserved_tasks"] = sum(
                len(tasks) for tasks in reserved.values()
            )

    except Exception as e:
        logger.warning(f"Failed to inspect Celery workers: {e}")

    # 2. Attempt Queue Depth check via Redis
    queues_to_check = ["celery", "default", "high_priority", "low_priority"]
    try:
        import redis

        broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
        if broker_url.startswith("redis"):
            r = redis.Redis.from_url(broker_url, socket_timeout=1.0)
            for q in queues_to_check:
                try:
                    length = r.llen(q)
                    if length > 0 or q in ["default", "celery"]:
                        stats_data["queues"][q] = length
                        stats_data["total_queue_depth"] += length
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"Failed to fetch Celery queue lengths from Redis: {e}")

    return stats_data


def broadcast_task_update(task_run):
    """
    Sends WebSocket update to 'celery_monitor' group if Channels is available.
    """
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                "celery_monitor",
                {
                    "type": "task_update",
                    "task_run": {
                        "task_id": task_run.task_id,
                        "task_name": task_run.task_name,
                        "status": task_run.status,
                        "started_at": (
                            task_run.started_at.isoformat()
                            if task_run.started_at
                            else None
                        ),
                        "finished_at": (
                            task_run.finished_at.isoformat()
                            if task_run.finished_at
                            else None
                        ),
                        "duration": task_run.duration,
                        "error_message": task_run.error_message,
                        "retry_count": task_run.retry_count,
                    },
                },
            )
    except Exception as e:
        logger.debug(f"Could not send WebSocket task update: {e}")


# Signal Listeners for automatic Celery Task monitoring
@task_prerun.connect
def on_task_prerun(sender=None, task_id=None, task=None, args=None, kwargs=None, **kw):
    if not task_id:
        return
    task_name = (sender.name if sender else None) or (
        task.name if task else "unknown_task"
    )
    args_repr = format_redacted_args(args=args, kwargs=kwargs)

    corr_id = ""
    if kwargs and isinstance(kwargs, dict):
        corr_id = str(kwargs.get("correlation_id") or "")
    if not corr_id and task and hasattr(task, "request"):
        headers = getattr(task.request, "headers", None) or {}
        corr_id = str(
            getattr(task.request, "correlation_id", None)
            or headers.get("correlation_id")
            or headers.get("X-Correlation-ID")
            or ""
        )
    if not corr_id:
        try:
            from apps.core.middleware.request_id import get_request_id

            corr_id = str(get_request_id() or "")
        except Exception:
            pass

    try:
        task_run, created = TaskRun.objects.get_or_create(
            task_id=task_id,
            defaults={
                "task_name": task_name,
                "correlation_id": corr_id,
                "status": "STARTED",
                "started_at": timezone.now(),
                "args_summary": args_repr,
            },
        )
        if not created:
            task_run.status = "STARTED"
            task_run.started_at = timezone.now()
            task_run.args_summary = args_repr
            if corr_id and not task_run.correlation_id:
                task_run.correlation_id = corr_id
            task_run.save()

        broadcast_task_update(task_run)
    except Exception as e:
        logger.error(f"Error handling task_prerun signal for {task_id}: {e}")


@task_postrun.connect
def on_task_postrun(
    sender=None, task_id=None, task=None, retval=None, state=None, **kw
):
    if not task_id:
        return
    task_name = (sender.name if sender else None) or (
        task.name if task else "unknown_task"
    )
    now = timezone.now()

    try:
        task_run = TaskRun.objects.filter(task_id=task_id).first()
        if not task_run:
            task_run = TaskRun(task_id=task_id, task_name=task_name, started_at=now)

        task_run.finished_at = now
        if task_run.started_at:
            task_run.duration = round((now - task_run.started_at).total_seconds(), 4)

        if state and state.upper() in ["SUCCESS", "FAILURE", "RETRY"]:
            task_run.status = state.upper()
        elif not task_run.status or task_run.status == "STARTED":
            task_run.status = "SUCCESS"

        task_run.save()
        broadcast_task_update(task_run)
    except Exception as e:
        logger.error(f"Error handling task_postrun signal for {task_id}: {e}")


@task_failure.connect
def on_task_failure(sender=None, task_id=None, exception=None, **kw):
    if not task_id:
        return
    now = timezone.now()
    error_str = str(exception)[:2000] if exception else "Unknown task failure"

    try:
        task_run = TaskRun.objects.filter(task_id=task_id).first()
        if not task_run:
            task_name = sender.name if sender else "unknown_task"
            task_run = TaskRun(task_id=task_id, task_name=task_name, started_at=now)

        task_run.status = "FAILURE"
        task_run.finished_at = now
        if task_run.started_at:
            task_run.duration = round((now - task_run.started_at).total_seconds(), 4)
        task_run.error_message = error_str
        task_run.save()
        broadcast_task_update(task_run)
    except Exception as e:
        logger.error(f"Error handling task_failure signal for {task_id}: {e}")


@task_retry.connect
def on_task_retry(sender=None, request=None, reason=None, **kw):
    task_id = request.id if request else None
    if not task_id:
        return
    reason_str = str(reason)[:2000] if reason else "Task retried"

    try:
        task_run = TaskRun.objects.filter(task_id=task_id).first()
        if not task_run:
            task_name = sender.name if sender else "unknown_task"
            task_run = TaskRun(
                task_id=task_id, task_name=task_name, started_at=timezone.now()
            )

        task_run.status = "RETRY"
        task_run.retry_count += 1
        task_run.error_message = reason_str
        task_run.save()
        broadcast_task_update(task_run)
    except Exception as e:
        logger.error(f"Error handling task_retry signal for {task_id}: {e}")


def get_task_type_stats():
    """
    Returns aggregated task statistics:
    - per_task_stats: total runs, successes, failures, avg duration, last failure reason
    - top_failing_tasks: top 5 tasks with highest failure count
    - sparkline_24h: hourly breakdown of total success vs failure for the last 24h
    """
    now = timezone.now()
    since_24h = now - timedelta(hours=24)

    task_names = (
        TaskRun.objects.exclude(task_name="")
        .values_list("task_name", flat=True)
        .order_by("task_name")
        .distinct()
    )
    per_task_stats = []

    for name in task_names:
        qs = TaskRun.objects.filter(task_name=name)
        total_runs = qs.count()
        successes = qs.filter(status="SUCCESS").count()
        failures = qs.filter(status="FAILURE").count()

        avg_duration_res = qs.filter(duration__isnull=False).aggregate(
            models.Avg("duration")
        )
        avg_duration = round(avg_duration_res["duration__avg"] or 0.0, 3)

        last_failed = (
            qs.filter(status="FAILURE").order_by("-finished_at", "-started_at").first()
        )
        last_failure_reason = last_failed.error_message if last_failed else None

        per_task_stats.append(
            {
                "task_name": name,
                "total_runs": total_runs,
                "successes": successes,
                "failures": failures,
                "avg_duration": avg_duration,
                "last_failure_reason": last_failure_reason,
            }
        )

    # Sort per_task_stats by total runs descending
    per_task_stats.sort(key=lambda x: x["total_runs"], reverse=True)

    # 2. Top-5 failing tasks
    top_failing_tasks = [t for t in per_task_stats if t["failures"] > 0]
    top_failing_tasks.sort(key=lambda x: x["failures"], reverse=True)
    top_failing_tasks = top_failing_tasks[:5]

    # 3. 24h sparkline hourly data
    sparkline_24h = []
    runs_24h = TaskRun.objects.filter(started_at__gte=since_24h)

    for hour in range(24):
        h_start = since_24h + timedelta(hours=hour)
        h_end = h_start + timedelta(hours=1)

        hour_qs = runs_24h.filter(started_at__gte=h_start, started_at__lt=h_end)
        succ = hour_qs.filter(status="SUCCESS").count()
        fail = hour_qs.filter(status="FAILURE").count()

        sparkline_24h.append(
            {
                "hour": h_start.strftime("%H:00"),
                "successes": succ,
                "failures": fail,
                "total": succ + fail,
            }
        )

    return {
        "per_task_stats": per_task_stats,
        "top_failing_tasks": top_failing_tasks,
        "sparkline_24h": sparkline_24h,
    }
