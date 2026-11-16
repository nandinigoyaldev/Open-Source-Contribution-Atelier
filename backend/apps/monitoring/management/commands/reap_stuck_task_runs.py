from django.core.management.base import BaseCommand

from apps.monitoring.job_ops import reap_expired_runs


class Command(BaseCommand):
    help = (
        "Marks running task runs whose lease expired as STUCK. The same work as the "
        "monitoring.reap_stuck_task_runs Celery beat task, for cron or a one-off run."
    )

    def handle(self, *args, **options):
        marked = reap_expired_runs()
        self.stdout.write(f"Marked {marked} task run(s) as stuck.")
