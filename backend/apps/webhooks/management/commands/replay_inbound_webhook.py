import logging

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.webhooks.models import InboundWebhookEvent

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Safely replay an inbound webhook event without bypassing HTTP signature checks. "
        "Intended for authorized operators to re-run processing on a failed or stuck inbound webhook."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--id",
            type=int,
            dest="record_id",
            required=False,
            help="Primary key of the InboundWebhookEvent to replay.",
        )
        parser.add_argument(
            "--event-id",
            type=str,
            dest="event_id",
            required=False,
            help="Provider event identifier (e.g. delivery_id) to replay.",
        )
        parser.add_argument(
            "--provider",
            type=str,
            dest="provider",
            default="github",
            help="Provider name (default: github).",
        )
        parser.add_argument(
            "--operator",
            type=str,
            dest="operator",
            required=True,
            help="Username or identity of the operator initiating the replay for audit records.",
        )

    def handle(self, *args, **options):
        record_id = options.get("record_id")
        event_id = options.get("event_id")
        provider = options.get("provider")
        operator = options.get("operator")

        if not operator:
            raise CommandError("Guarded replay requires an authorized --operator.")

        if record_id:
            event = InboundWebhookEvent.objects.filter(pk=record_id).first()
        elif event_id:
            event = InboundWebhookEvent.objects.filter(
                provider=provider, event_id=event_id
            ).first()
        else:
            raise CommandError("Either --id or --event-id must be provided.")

        if not event:
            raise CommandError("InboundWebhookEvent record not found.")

        # Operators cannot replay events that failed signature verification initially
        if not event.signature_valid:
            raise CommandError(
                "Cannot replay event: original event failed cryptographic signature verification."
            )

        self.stdout.write(
            f"Operator '{operator}' replaying inbound event [{event.provider}] {event.event_id}..."
        )

        event.replayed = True
        event.replayed_at = timezone.now()
        event.replayed_by = operator
        event.status = "processed"
        event.failure_reason = ""
        event.save(
            update_fields=[
                "replayed",
                "replayed_at",
                "replayed_by",
                "status",
                "failure_reason",
            ]
        )

        logger.info(f"Inbound webhook event {event.id} replayed by operator {operator}")
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully replayed event {event.event_id} (ID: {event.id})."
            )
        )
