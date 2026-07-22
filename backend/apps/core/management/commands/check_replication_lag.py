"""
Management command: check_replication_lag

Usage:
    python manage.py check_replication_lag [--alert-threshold SECONDS]

Queries each configured read replica for its replication lag and prints
a formatted report. Exits with code 1 if any replica exceeds the threshold
or is unreachable.
"""

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    help = "Check replication lag on all configured read replicas."

    def add_arguments(self, parser):
        parser.add_argument(
            "--alert-threshold",
            type=float,
            default=None,
            help=(
                "Lag in seconds above which the command exits with code 1. "
                "Defaults to settings.REPLICA_LAG_ALERT_SECONDS (30s)."
            ),
        )

    def handle(self, *args, **options):
        from config.db_router import PrimaryReplicaRouter

        threshold = options["alert_threshold"] or getattr(
            settings, "REPLICA_LAG_ALERT_SECONDS", 30
        )
        router = PrimaryReplicaRouter()

        if not router.replicas:
            self.stdout.write(
                self.style.WARNING("No replicas configured. Nothing to check.")
            )
            return

        self.stdout.write(
            self.style.HTTP_INFO(
                f"\nChecking replication lag (alert threshold: {threshold}s)\n"
            )
        )

        lag_info = router.get_replica_lag_info()
        any_bad = False

        for replica in lag_info:
            alias = replica["alias"]
            lag = replica.get("lag_seconds")
            status = replica["status"]
            error = replica.get("error", "")

            if status == "error":
                self.stdout.write(self.style.ERROR(f"  ✗ {alias}: ERROR — {error}"))
                any_bad = True
            elif lag is not None and lag > threshold:
                self.stdout.write(
                    self.style.WARNING(
                        f"  ⚠ {alias}: LAGGING — {lag}s (threshold: {threshold}s)"
                    )
                )
                any_bad = True
            else:
                lag_display = f"{lag}s" if lag is not None else "N/A (SQLite?)"
                self.stdout.write(
                    self.style.SUCCESS(f"  ✓ {alias}: OK — lag={lag_display}")
                )

        self.stdout.write("")

        if any_bad:
            raise CommandError(
                "One or more replicas are lagging or unreachable. See output above."
            )

        self.stdout.write(
            self.style.SUCCESS("All replicas are within acceptable lag threshold.")
        )
