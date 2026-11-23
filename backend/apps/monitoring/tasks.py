from celery import shared_task
from django.core.management import call_command


@shared_task
def verify_latest_backup():
    """
    Weekly celery task to verify the latest database backup.
    """
    call_command("verify_backup")


@shared_task(name="monitoring.reap_stuck_task_runs")
def reap_stuck_task_runs():
    """
    Mark running task runs whose lease expired as STUCK. Run it every minute from
    Celery beat; running it twice in a row is harmless.
    """
    from apps.monitoring.job_ops import reap_expired_runs

    return {"marked_stuck": reap_expired_runs()}


@shared_task(name="monitoring.requeue_orphaned_runs")
def requeue_orphaned_runs():
    """
    Send runs that lost their worker again, for tasks that opted in with
    ``failover_requeue=True``. Run it right after the reaper; running it twice in a
    row is harmless.
    """
    from apps.monitoring.job_ops import requeue_orphaned_runs as requeue

    return requeue()
