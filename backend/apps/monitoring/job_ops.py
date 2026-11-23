# pyright: reportAttributeAccessIssue=false, reportIndexIssue=false, reportOperatorIssue=false, reportArgumentType=false, reportReturnType=false, reportGeneralTypeIssues=false, reportCallIssue=false
"""
Operator actions on background jobs: leases, the stuck-run reaper, cancel and retry.

Every state change is a conditional ``UPDATE ... WHERE status IN (...)`` and the row
count says whether this caller won. That is what makes the actions idempotent: a
second click, a double submit or a reaper pass that overlaps another finds nothing
left to change, does nothing and writes no second audit event.

Lease lifecycle of a TaskRun:

* ``task_prerun`` takes the lease: ``heartbeat_at`` = now, ``lease_expires_at`` = now
  + the task's ``time_limit`` plus a grace period, or ``TASK_RUN_LEASE_SECONDS`` when
  the task has no time limit.
* A long task can call ``touch_heartbeat(task_id)`` to push the lease forward.
* ``task_postrun`` / ``task_failure`` / ``task_retry`` release it.
* ``reap_expired_runs`` marks a STARTED run whose lease ran out as STUCK.
* ``requeue_orphaned_runs`` sends a STUCK run of an opted-in task again, once.
"""

import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Optional

from celery import current_app
from django.conf import settings
from django.db.models import F
from django.utils import timezone

from apps.audit.admin_events import record_admin_event, target_type_for
from apps.audit.models import AuditEvent
from apps.monitoring.models import TaskRun

logger = logging.getLogger(__name__)

OP_MARKED_STUCK = "task_run.marked_stuck"
OP_CANCELLED = "task_run.cancelled"
OP_RETRIED = "task_run.retried"

# Statuses an operator may act on.
RETRYABLE = ("FAILURE", "STUCK", "CANCELLED")
CANCELLABLE = ("PENDING", "RETRY", "STUCK")
# A retry or cancel on one of these is a no-op that reports the current state.
ALREADY_RETRIED = ("PENDING", "STARTED", "RETRY")

# Seconds added to a task's time_limit before its lease expires.
LEASE_GRACE_SECONDS = 60
# Runs marked stuck per reaper pass, so one pass after a long outage stays short.
REAP_BATCH_SIZE = 500


def default_lease_seconds() -> int:
    return int(getattr(settings, "TASK_RUN_LEASE_SECONDS", 900))


def lease_seconds_for(task: Any = None) -> int:
    time_limit = getattr(task, "time_limit", None)
    if isinstance(time_limit, (int, float)) and time_limit > 0:
        return int(time_limit) + LEASE_GRACE_SECONDS
    return default_lease_seconds()


def touch_heartbeat(task_id: str, lease_seconds: Optional[int] = None) -> bool:
    """
    Record that the worker is alive and push the lease out. Long-running tasks call
    this from their loop. A run the reaper already marked STUCK goes back to STARTED,
    because a heartbeat proves the worker did not die. Returns False when there is no
    live run to touch (finished, cancelled or unknown).
    """
    now = timezone.now()
    seconds = lease_seconds if lease_seconds is not None else default_lease_seconds()
    updated = TaskRun.objects.filter(
        task_id=task_id, status__in=("STARTED", "STUCK")
    ).update(
        status="STARTED",
        heartbeat_at=now,
        lease_expires_at=now + timedelta(seconds=seconds),
    )
    return bool(updated)


def reap_expired_runs(now=None) -> int:
    """
    Mark every STARTED run whose lease expired as STUCK, with an audit event each.
    Safe to run concurrently and repeatedly: only the pass that flips a row records it.
    """
    from apps.monitoring.celery_monitor import broadcast_task_update

    now = now or timezone.now()
    expired = list(
        TaskRun.objects.filter(status="STARTED", lease_expires_at__lt=now).values_list(
            "pk", "lease_expires_at"
        )[:REAP_BATCH_SIZE]
    )
    marked = 0
    for pk, lease_expires_at in expired:
        reason = (
            f"Lease expired at {lease_expires_at.isoformat()} "
            "without a heartbeat or a result from the worker."
        )
        flipped = TaskRun.objects.filter(
            pk=pk, status="STARTED", lease_expires_at__lt=now
        ).update(status="STUCK", error_message=reason)
        if not flipped:
            continue
        marked += 1
        run = TaskRun.objects.get(pk=pk)
        record_admin_event(
            operation=OP_MARKED_STUCK,
            action=AuditEvent.ACTION_UPDATED,
            target_type=target_type_for(TaskRun),
            target_id=run.pk,
            payload={
                "task_id": run.task_id,
                "task_name": run.task_name,
                "from_status": "STARTED",
                "to_status": "STUCK",
                "lease_expires_at": lease_expires_at.isoformat(),
            },
        )
        broadcast_task_update(run)
    return marked


def is_requeue_safe(run: TaskRun) -> bool:
    """
    A STUCK run may be re-sent on its own only when that cannot do harm: the task is
    opted in (``failover_requeue=True`` on the task, or its name in
    ``FAILOVER_REQUEUE_TASKS``) because a worker that was only slow may still finish
    the first copy, so the task has to be idempotent. Runs with arguments never
    qualify, since arguments are not stored and cannot be replayed.
    """
    if run.args_summary:
        return False
    if run.task_name in set(getattr(settings, "FAILOVER_REQUEUE_TASKS", ()) or ()):
        return True
    task = current_app.tasks.get(run.task_name)
    return bool(getattr(task, "failover_requeue", False))


def requeue_orphaned_runs(now=None) -> dict:
    """
    Failover for jobs whose worker died: dispatch each STUCK run of an opted-in task
    again. Exactly once per run, because ``retry_run`` claims the row with a
    conditional update, so overlapping passes or a pass repeated after a crash find
    the run already in RETRY. A task that keeps dying is not retried forever: after
    ``FAILOVER_REQUEUE_MAX_ATTEMPTS`` requeues inside
    ``FAILOVER_REQUEUE_WINDOW_SECONDS`` the remaining runs are left STUCK for an
    operator. Stops at the first broker error, nothing is lost since the run stays STUCK.
    """
    now = now or timezone.now()
    max_attempts = int(getattr(settings, "FAILOVER_REQUEUE_MAX_ATTEMPTS", 3))
    window = timedelta(
        seconds=int(getattr(settings, "FAILOVER_REQUEUE_WINDOW_SECONDS", 3600))
    )
    counts = {
        "requeued": 0,
        "skipped_unsafe": 0,
        "skipped_exhausted": 0,
        "broker_unavailable": 0,
    }
    stuck = TaskRun.objects.filter(status="STUCK").order_by("started_at")
    for run in stuck[:REAP_BATCH_SIZE]:
        if not is_requeue_safe(run):
            counts["skipped_unsafe"] += 1
            continue
        # Every requeue leaves the original row in RETRY, so those rows are the tally.
        attempts = TaskRun.objects.filter(
            task_name=run.task_name, status="RETRY", started_at__gte=now - window
        ).count()
        if attempts >= max_attempts:
            counts["skipped_exhausted"] += 1
            continue
        outcome = retry_run(run, None)
        if outcome.state == "queued":
            counts["requeued"] += 1
        elif outcome.state == "broker_unavailable":
            counts["broker_unavailable"] += 1
            break
    return counts


@dataclass
class ActionResult:
    """Outcome of an operator action: ``state`` is machine readable, ``http`` the status code."""

    state: str
    http: int
    message: str
    extra: dict = field(default_factory=dict)

    def body(self, run: TaskRun) -> dict:
        return {
            "status": self.state,
            "task_id": run.task_id,
            "run_status": run.status,
            "retry_count": run.retry_count,
            "message": self.message,
            **self.extra,
        }


def _claim(run: TaskRun, from_statuses: tuple, **changes: Any) -> bool:
    """Move the run out of ``from_statuses`` atomically. True when this caller did it."""
    return bool(
        TaskRun.objects.filter(pk=run.pk, status__in=from_statuses).update(**changes)
    )


def cancel_run(run: TaskRun, request: Any) -> ActionResult:
    """
    Cancel a run that is waiting (PENDING, RETRY) or presumed dead (STUCK). A RUNNING
    run is refused: revoking it would not stop it, and once its lease expires it
    shows up as STUCK and can be cancelled then. Cancelling a STUCK run also tells the
    worker to terminate the task, since its process is hung or gone.
    """
    run.refresh_from_db()
    if run.status == "CANCELLED":
        return ActionResult("already_cancelled", 200, "Task run is already cancelled.")
    if run.status not in CANCELLABLE:
        return ActionResult(
            "not_cancellable",
            409,
            f"A {run.status.lower()} task run cannot be cancelled.",
        )

    previous, previous_finished_at = run.status, run.finished_at
    if not _claim(
        run,
        CANCELLABLE,
        status="CANCELLED",
        finished_at=timezone.now(),
        lease_expires_at=None,
    ):
        # Lost a race with another action; report what the row is now.
        run.refresh_from_db()
        if run.status == "CANCELLED":
            return ActionResult(
                "already_cancelled", 200, "Task run is already cancelled."
            )
        return ActionResult(
            "conflict", 409, "Task run changed while cancelling, try again."
        )

    try:
        current_app.control.revoke(run.task_id, terminate=previous == "STUCK")
    except Exception:
        logger.exception("Could not revoke task %s", run.task_id)
        TaskRun.objects.filter(pk=run.pk, status="CANCELLED").update(
            status=previous, finished_at=previous_finished_at
        )
        return ActionResult(
            "broker_unavailable",
            503,
            "Could not reach the broker to revoke the task. Nothing was changed.",
        )

    run.refresh_from_db()
    record_admin_event(
        operation=OP_CANCELLED,
        action=AuditEvent.ACTION_UPDATED,
        target_type=target_type_for(TaskRun),
        target_id=run.pk,
        request=request,
        payload={
            "task_id": run.task_id,
            "task_name": run.task_name,
            "from_status": previous,
            "to_status": "CANCELLED",
            "terminated": previous == "STUCK",
        },
    )
    return ActionResult("cancelled", 200, f"Task '{run.task_name}' cancelled.")


def retry_run(run: TaskRun, request: Any) -> ActionResult:
    """
    Re-dispatch a FAILURE, STUCK or CANCELLED run. The original row moves to RETRY and
    its retry_count goes up, so a second retry on it is answered with
    ``already_queued`` instead of dispatching twice. The new message gets a new task id
    and its own run row.

    Arguments are not replayed: only a redacted summary of them is stored, so the task
    is dispatched with none. Tasks that need arguments must be re-run from their source.
    """
    run.refresh_from_db()
    if run.status in ALREADY_RETRIED:
        return ActionResult(
            "already_queued",
            200,
            f"Task '{run.task_name}' is already {run.status.lower()}.",
        )
    if run.status not in RETRYABLE:
        return ActionResult(
            "not_retryable",
            409,
            f"A {run.status.lower()} task run cannot be retried.",
        )

    previous = run.status
    if not _claim(
        run,
        RETRYABLE,
        status="RETRY",
        retry_count=F("retry_count") + 1,
        started_at=timezone.now(),
        lease_expires_at=None,
    ):
        run.refresh_from_db()
        return ActionResult(
            "already_queued",
            200,
            f"Task '{run.task_name}' is already {run.status.lower()}.",
        )

    try:
        new_task_id = current_app.send_task(run.task_name).id
    except Exception:
        logger.exception("Could not dispatch retry of task %s", run.task_id)
        TaskRun.objects.filter(pk=run.pk, status="RETRY").update(
            status=previous, retry_count=F("retry_count") - 1
        )
        return ActionResult(
            "broker_unavailable",
            503,
            "Could not reach the broker to dispatch the task. Nothing was changed.",
        )

    run.refresh_from_db()
    record_admin_event(
        operation=OP_RETRIED,
        action=AuditEvent.ACTION_UPDATED,
        target_type=target_type_for(TaskRun),
        target_id=run.pk,
        request=request,
        payload={
            "task_id": run.task_id,
            "task_name": run.task_name,
            "from_status": previous,
            "to_status": "RETRY",
            "retry_count": run.retry_count,
            "new_task_id": new_task_id,
        },
    )
    return ActionResult(
        "queued",
        202,
        f"Task '{run.task_name}' dispatched for retry.",
        {"new_task_id": new_task_id},
    )
