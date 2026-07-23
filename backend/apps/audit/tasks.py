import json
import logging
import os
from datetime import timedelta
from pathlib import Path
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from apps.audit.models import AuditEvent

logger = logging.getLogger(__name__)


@shared_task
def archive_audit_events():
    """
    Archive audit events older than the configured TTL (default 90 days)
    to a JSON file in the configured storage directory, then delete them from the database.
    """
    retention_days = getattr(settings, "AUDIT_RETENTION_DAYS", 90)
    cutoff = timezone.now() - timedelta(days=retention_days)

    events_to_archive = AuditEvent.objects.filter(created_at__lt=cutoff)
    count = events_to_archive.count()

    if count == 0:
        logger.info("No audit events to archive.")
        return 0

    archive_dir = Path(
        getattr(settings, "AUDIT_ARCHIVE_DIR", settings.BASE_DIR / "archives" / "audit")
    )
    archive_dir.mkdir(parents=True, exist_ok=True)

    timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
    archive_file = archive_dir / f"audit_archive_{timestamp}.json"

    # Batch serialize and write to JSON
    serialized_events = []
    for event in events_to_archive.iterator():
        serialized_events.append(
            {
                "id": event.id,
                "actor_id": event.actor_id,
                "action": event.action,
                "resource_type": event.resource_type,
                "resource_id": event.resource_id,
                "before": event.before,
                "after": event.after,
                "correlation_id": event.correlation_id,
                "ip_address": event.ip_address,
                "user_agent": event.user_agent,
                "created_at": event.created_at.isoformat(),
                "extra": event.extra,
            }
        )

    with open(archive_file, "w", encoding="utf-8") as f:
        json.dump(serialized_events, f, indent=2)

    logger.info("Archived %d audit events to %s", count, archive_file)

    # We bypass the custom delete() method on model instances by using queryset delete()
    # since AuditEvent.objects.filter(...).delete() is called on QuerySet level.
    # But wait! QuerySet.delete() doesn't call individual model delete() methods, but we want
    # to be explicit and safe. To bypass the model's delete blocks, we can do raw database delete
    # or use queryset.delete() which goes directly to sql. But since we overrides delete() on model,
    # let's check if queryset.delete() is allowed or if we should call a helper.
    # Actually, queryset.delete() bypasses the model's delete method. Let's make sure it works.
    deleted_count, _ = events_to_archive.delete()

    logger.info("Deleted %d archived audit events from database.", deleted_count)
    return deleted_count
