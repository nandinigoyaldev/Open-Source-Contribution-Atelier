from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

from apps.errors.models import ErrorGroup, ErrorEvent
from apps.errors.grouping import normalize_message, calculate_fingerprint

logger = logging.getLogger(__name__)


@shared_task
def ingest_error_event_task(payload):
    """
    Ingests and processes an incoming error event asynchronously.
    Normalizes the error message, calculates the group fingerprint,
    manages resolved/reopened state, and records the event.
    """
    raw_message = payload.get("message", "")
    stacktrace = payload.get("stacktrace", "")
    module = payload.get("module", "default")
    request_id = payload.get("request_id")
    user_id = payload.get("user_id")
    metadata = payload.get("metadata", {})
    timestamp_str = payload.get("timestamp")

    if timestamp_str:
        try:
            timestamp = timezone.datetime.fromisoformat(timestamp_str)
            if timezone.is_naive(timestamp):
                timestamp = timezone.make_aware(timestamp)
        except ValueError:
            timestamp = timezone.now()
    else:
        timestamp = timezone.now()

    # Step 1: Normalize and calculate fingerprint
    normalized = normalize_message(raw_message)
    fingerprint = calculate_fingerprint(normalized, stacktrace, module)

    # Step 2: Fetch or create ErrorGroup
    group, created = ErrorGroup.objects.get_or_create(
        fingerprint=fingerprint,
        defaults={
            "message": normalized,
            "module": module,
            "status": "new",
            "first_seen": timestamp,
        },
    )

    # Step 3: Handle reopening workflow for resolved groups
    now = timezone.now()
    if not created:
        if group.status == "resolved" and group.resolved_at:
            cooldown_period = timedelta(days=group.cooldown_days)
            if now >= group.resolved_at + cooldown_period:
                group.status = "new"
                group.resolved_at = None
                logger.info(
                    f"Reopened resolved error group {group.id} due to cooldown expiration."
                )

        group.count += 1
        group.last_seen = now
        group.save(update_fields=["count", "last_seen", "status", "resolved_at"])
    else:
        group.count = 1
        group.save(update_fields=["count"])

    # Step 4: Create ErrorEvent
    event = ErrorEvent.objects.create(
        group=group,
        raw_message=raw_message,
        stacktrace=stacktrace,
        request_id=request_id,
        user_id=user_id,
        timestamp=timestamp,
        metadata=metadata,
    )

    logger.debug(f"Ingested event {event.id} for group {group.id}")
    return event.id
