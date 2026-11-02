from django.core.management.base import BaseCommand

from apps.notifications.retention import purge_notification_ledger, retention_windows


class Command(BaseCommand):
    help = (
        "Delete old notification attempts, deliveries and dead letters according to the "
        "NOTIFICATION_*_RETENTION_DAYS settings. Pending deliveries are never deleted."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only report how many rows would be removed.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Rows deleted per statement (default 1000).",
        )

    def handle(self, *args, **options):
        windows = retention_windows()
        self.stdout.write(
            "Retention (days, 0 = keep): "
            + ", ".join(f"{name}={days}" for name, days in windows.items())
        )
        counts = purge_notification_ledger(
            dry_run=options["dry_run"], batch_size=options["batch_size"]
        )
        verb = "Would remove" if options["dry_run"] else "Removed"
        for name, n in counts.items():
            self.stdout.write(f"{verb} {n} {name.replace('_', ' ')}")
