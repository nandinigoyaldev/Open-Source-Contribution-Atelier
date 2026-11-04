import logging
from datetime import timedelta
from typing import Any, cast

from django.db.models import Q
from django.utils import timezone

from . import runner
from .models import ExportJob

logger = logging.getLogger(__name__)

try:
    from celery import shared_task
except ImportError:  # pragma: no cover

    def shared_task(*args, **kwargs):
        if len(args) == 1 and callable(args[0]):
            return args[0]

        def decorator(func):
            return func

        return decorator


# Files that no job row accounts for are only removed once they are this old, so a job that has
# just created its part file is never mistaken for an orphan.
ORPHAN_GRACE = timedelta(hours=24)


@shared_task(name="data_exports.run_export_job")
def run_export_job(job_id):
    """Run or resume one export. Safe to call more than once for the same job."""
    return runner.run_job(job_id)


def enqueue(job_id, delay: int = 0) -> None:
    """Hand a job to a worker. If that fails the job stays queued and the sweep picks it up."""
    try:
        # the task decorator is not understood by the type checker, hence the cast
        cast(Any, run_export_job).apply_async(args=(str(job_id),), countdown=delay)
    except Exception as exc:
        logger.warning("Could not queue export %s: %s", job_id, exc)


@shared_task(name="data_exports.sweep_exports")
def sweep_exports() -> dict:
    """
    Keep the pipeline moving and the disk clean. Run it every couple of minutes.

    * A running job whose worker stopped sending heartbeats goes back to the queue and resumes from
      its checkpoint, or fails once it has used all its attempts.
    * Queued jobs that are due, or that nobody picked up, are queued again; a cancel request on a
      job that never started takes effect at once.
    * Finished exports are deleted when their download window closes; failed and cancelled jobs
      leave no files behind; files that belong to no job are removed.
    """
    now = timezone.now()
    summary = {
        "requeued": 0,
        "failed": 0,
        "cancelled": 0,
        "expired": 0,
        "files_removed": 0,
    }

    # 1. workers that died
    cutoff = now - timedelta(seconds=runner.lease_seconds())
    for job in list(
        ExportJob.objects.filter(status=ExportJob.RUNNING, heartbeat_at__lt=cutoff)[
            :200
        ]
    ):
        if job.attempts >= runner.max_attempts():
            changed = ExportJob.objects.filter(
                pk=job.pk, status=ExportJob.RUNNING, heartbeat_at__lt=cutoff
            ).update(
                status=ExportJob.FAILED,
                lease_token=None,
                finished_at=now,
                error="Gave up after repeated worker failures",
            )
            if changed:
                runner.remove_file(runner.part_path(job))
                summary["failed"] += 1
        else:
            changed = ExportJob.objects.filter(
                pk=job.pk, status=ExportJob.RUNNING, heartbeat_at__lt=cutoff
            ).update(status=ExportJob.QUEUED, lease_token=None, next_run_at=None)
            if changed:
                enqueue(job.pk)
                summary["requeued"] += 1

    # 2. queued jobs
    unattended = now - timedelta(seconds=runner.lease_seconds())
    queued = ExportJob.objects.filter(status=ExportJob.QUEUED).filter(
        Q(next_run_at__lte=now) | Q(next_run_at__isnull=True, created_at__lt=unattended)
    )
    for job in list(queued[:200]):
        if job.cancel_requested:
            changed = ExportJob.objects.filter(
                pk=job.pk, status=ExportJob.QUEUED
            ).update(status=ExportJob.CANCELLED, finished_at=now)
            if changed:
                runner.remove_file(runner.part_path(job))
                summary["cancelled"] += 1
        else:
            enqueue(job.pk)
            summary["requeued"] += 1

    # 3. downloads that are past their window
    for job in list(
        ExportJob.objects.filter(status=ExportJob.COMPLETED, expires_at__lt=now)[:200]
    ):
        changed = ExportJob.objects.filter(
            pk=job.pk, status=ExportJob.COMPLETED
        ).update(status=ExportJob.EXPIRED)
        if changed:
            runner.remove_file(runner.final_path(job))
            summary["expired"] += 1

    # 4. files nothing needs any more
    summary["files_removed"] += _remove_stray_files(now)

    if any(summary.values()):
        logger.info("Export sweep: %s", summary)
    return summary


def _remove_stray_files(now) -> int:
    root = runner.export_root()
    removed = 0
    for path in root.iterdir():
        if not path.is_file() or not runner.FILE_NAME.match(path.name):
            continue  # never touch anything this pipeline did not create
        job_id = path.name.split(".")[0]
        job = ExportJob.objects.filter(pk=job_id).only("status", "file_format").first()
        if job is None:
            age = now.timestamp() - path.stat().st_mtime
            stray = age > ORPHAN_GRACE.total_seconds()
        elif job.status in (ExportJob.FAILED, ExportJob.CANCELLED, ExportJob.EXPIRED):
            stray = True
        elif job.status == ExportJob.COMPLETED:
            stray = path.suffix == ".part"  # leftover next to a finished file
        else:
            stray = False
        if stray:
            runner.remove_file(path)
            removed += 1
    return removed
