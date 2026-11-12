"""
Management command to clean up expired idempotency records.
"""

from django.core.management.base import BaseCommand
from apps.deduplication.idempotency import cleanup_expired_records


class Command(BaseCommand):
    """
    Delete expired idempotency records to prevent unbounded table growth.

    Usage:
        python manage.py cleanup_expired_idempotency_records
    """

    help = "Delete expired idempotency records"

    def handle(self, *args, **options):
        deleted_count = cleanup_expired_records()
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully deleted {deleted_count} expired idempotency record(s)."
            )
        )
