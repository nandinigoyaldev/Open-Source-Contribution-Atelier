from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.monitoring.models import TaskRun


class Command(BaseCommand):
    help = "Cleans up task run records older than a retention threshold (default: 30 days)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Number of days of task runs to retain (default: 30).",
        )

    def handle(self, *args, **options):
        days = options.get("days", 30)
        cutoff = timezone.now() - timedelta(days=days)
        deleted_count, _ = TaskRun.objects.filter(started_at__lt=cutoff).delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully deleted {deleted_count} task run(s) older than {days} days."
            )
        )
