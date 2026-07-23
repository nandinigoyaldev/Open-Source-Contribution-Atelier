from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.issues.models import Issue


class Command(BaseCommand):
    help = "Check for stale issue assignments (timezone-aware)"

    def handle(self, *args, **options):
        now = timezone.now()

        # 2 days + 2 hour buffer for timezone offset
        stale_threshold = now - timedelta(days=2, hours=2)

        stale_issues = Issue.objects.filter(
            assigned_at__lte=stale_threshold, status="assigned"
        )

        count = stale_issues.count()
        for issue in stale_issues:
            self.stdout.write(
                f"Unassigning issue #{issue.id} (assigned {issue.assigned_at})"
            )
            issue.status = "open"
            issue.assigned_to = None
            issue.save()

        self.stdout.write(self.style.SUCCESS(f"✅ Unassigned {count} stale issues"))
