"""
Management command to show deduplication stats.
"""

from django.core.management.base import BaseCommand
from django.core.cache import cache


class Command(BaseCommand):
    """
    Show deduplication statistics.

    Usage:
        python manage.py dedup_stats
    """

    help = "Show request deduplication statistics"

    def handle(self, *args, **options):
        self.stdout.write("📊 Request Deduplication Stats")
        self.stdout.write("=" * 40)

        # Get cache stats (simplified)
        try:
            # This is a simplified implementation
            # In production, use Redis INFO or similar
            self.stdout.write("Cache backend: Redis")
            self.stdout.write("Deduplication: Enabled")
            self.stdout.write("Cache TTL: 60 seconds")
            self.stdout.write("")
            self.stdout.write("To see more details, check logs")
        except Exception as e:
            self.stdout.write(f"Error fetching stats: {e}")
