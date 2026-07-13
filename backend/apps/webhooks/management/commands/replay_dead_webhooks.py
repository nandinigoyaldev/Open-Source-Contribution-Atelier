import logging

from django.core.management.base import BaseCommand

from apps.webhooks.models import DeadLetterWebhook
from apps.webhooks.tasks import replay_delivery

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Replay webhook deliveries from the Dead Letter Queue. "
        "By default, replays all non-replayed entries. "
        "Use --id to replay a specific DLQ entry."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--id",
            type=int,
            dest="dlq_id",
            default=None,
            help="ID of a specific DeadLetterWebhook entry to replay.",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            dest="replay_all",
            help="Replay ALL dead-lettered webhooks, including previously replayed ones.",
        )

    def handle(self, *args, **options):
        dlq_id = options.get("dlq_id")
        replay_all = options.get("replay_all", False)

        if dlq_id:
            self.stdout.write(f"Replaying DLQ entry {dlq_id}...")
            replay_delivery(dlq_id)
            self.stdout.write(self.style.SUCCESS(f"Queued replay for DLQ entry {dlq_id}."))
            return

        qs = DeadLetterWebhook.objects.all()
        if not replay_all:
            qs = qs.filter(replayed=False)

        count = qs.count()
        if count == 0:
            self.stdout.write("No dead-lettered webhooks to replay.")
            return

        self.stdout.write(f"Replaying {count} DLQ entries...")
        for entry in qs:
            replay_delivery(entry.id)

        self.stdout.write(
            self.style.SUCCESS(f"Successfully queued {count} webhook(s) for replay.")
        )
