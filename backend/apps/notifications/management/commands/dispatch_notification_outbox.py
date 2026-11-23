import time

from django.core.management.base import BaseCommand

from apps.notifications.outbox import batch_size, dispatch_due


class Command(BaseCommand):
    help = (
        "Hand due notification outbox rows to the delivery ledger. Runs one sweep and exits; "
        "use --watch to keep sweeping (for a dedicated worker process without Celery beat)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=None,
            help="Rows claimed per batch (default NOTIFICATION_OUTBOX_BATCH_SIZE).",
        )
        parser.add_argument(
            "--max-rows",
            type=int,
            default=500,
            help="Stop a sweep after this many rows (default 500).",
        )
        parser.add_argument(
            "--watch",
            action="store_true",
            help="Sweep forever, sleeping --interval seconds between sweeps.",
        )
        parser.add_argument(
            "--interval",
            type=float,
            default=5.0,
            help="Seconds between sweeps with --watch (default 5).",
        )

    def handle(self, *args, **options):
        size = options["batch_size"] or batch_size()
        while True:
            summary = dispatch_due(limit=size, max_rows=options["max_rows"])
            self.stdout.write(
                ", ".join(f"{name}={count}" for name, count in summary.items())
            )
            if not options["watch"]:
                return
            time.sleep(options["interval"])
