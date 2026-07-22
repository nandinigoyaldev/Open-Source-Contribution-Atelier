"""
Celery tasks for async event processing.
"""

import logging
from django.db import transaction
from apps.events.models import DomainEvent
from apps.events.services.event_bus import EventBus

logger = logging.getLogger(__name__)


def process_event(event_id: str):
    """
    Process a domain event asynchronously.

    Args:
        event_id: UUID of the domain event
    """
    try:
        event = DomainEvent.objects.get(id=event_id)
    except DomainEvent.DoesNotExist:
        logger.error(f"Event {event_id} not found")
        return

    # Mark as processing
    event.mark_processing()

    try:
        # Get event type handlers
        event_type = event.event_type
        handlers = EventBus._handlers.get(event_type, [])

        if not handlers:
            event.mark_completed()
            logger.info(f"No handlers for event type {event_type}")
            return

        # Process handlers
        with transaction.atomic():
            EventBus._process_handlers(event, handlers)
            event.mark_completed()

        logger.info(f"Event {event_id} processed successfully")

    except Exception as e:
        # Handle failure
        logger.error(f"Failed to process event {event_id}: {e}", exc_info=True)

        if event.should_retry():
            # Retry with exponential backoff
            event.mark_retry()
            # Django-Q doesn't have self.retry, we can enqueue it again if needed or let Django-Q handle it.
            # For manual retry:
            from django_q.tasks import async_task

            async_task("apps.events.tasks.process_event", str(event.id))
        else:
            # Max retries exceeded
            event.mark_failed(str(e))
            logger.error(f"Event {event_id} failed after {event.retry_count} retries")


def retry_failed_events():
    """
    Scheduled task to retry failed events.
    """
    from django.utils import timezone
    from datetime import timedelta
    from django.db import models
    from django_q.tasks import async_task

    # Get events that failed and are eligible for retry
    failed_events = DomainEvent.objects.filter(
        status=DomainEvent.STATUS_FAILED, retry_count__lt=models.F("max_retries")
    )

    count = 0
    for event in failed_events:
        event.mark_retry()
        async_task("apps.events.tasks.process_event", str(event.id))
        count += 1

    logger.info(f"Retried {count} failed events")


def cleanup_old_events():
    """
    Clean up old completed events.
    """
    from django.utils import timezone
    from datetime import timedelta

    # Delete events older than 30 days
    cutoff = timezone.now() - timedelta(days=30)
    deleted = DomainEvent.objects.filter(
        status=DomainEvent.STATUS_COMPLETED, occurred_at__lt=cutoff
    ).delete()

    logger.info(f"Cleaned up {deleted[0]} old events")
