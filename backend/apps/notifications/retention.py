"""
Retention for the notification delivery ledger.

Without a limit the attempt log and the delivery table grow with every notification ever sent.
``purge_notification_ledger`` removes old rows in bounded batches. It never touches a delivery
that is still ``pending`` (still waiting to be delivered or retried), and a window of 0 keeps
that kind of row forever.

Settings (days):

* ``NOTIFICATION_ATTEMPT_RETENTION_DAYS`` (default 30): attempt rows, the detailed log.
* ``NOTIFICATION_DELIVERY_RETENTION_DAYS`` (default 90): delivered rows (sent, opened, clicked, bounced).
* ``NOTIFICATION_FAILED_RETENTION_DAYS`` (default 180): failed deliveries and dead letters, kept
  longer because they are what someone investigates.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import NotificationAttempt, NotificationDeadLetter, NotificationDelivery

logger = logging.getLogger(__name__)

DEFAULT_ATTEMPT_DAYS = 30
DEFAULT_DELIVERY_DAYS = 90
DEFAULT_FAILED_DAYS = 180

DELIVERED_STATUSES = ("sent", "opened", "clicked", "bounced", "batched", "cancelled")


def retention_windows() -> dict:
    """The configured windows in days; ``0`` means keep forever."""

    def days(name, default):
        try:
            return max(0, int(getattr(settings, name, default)))
        except (TypeError, ValueError):
            return default

    return {
        "attempts": days("NOTIFICATION_ATTEMPT_RETENTION_DAYS", DEFAULT_ATTEMPT_DAYS),
        "deliveries": days(
            "NOTIFICATION_DELIVERY_RETENTION_DAYS", DEFAULT_DELIVERY_DAYS
        ),
        "failed": days("NOTIFICATION_FAILED_RETENTION_DAYS", DEFAULT_FAILED_DAYS),
    }


def _delete_in_batches(queryset, batch_size: int) -> int:
    """Delete a queryset a batch at a time so no single statement holds locks for long."""
    model = queryset.model
    deleted = 0
    while True:
        ids = list(queryset.values_list("pk", flat=True)[:batch_size])
        if not ids:
            return deleted
        model.objects.filter(pk__in=ids).delete()
        deleted += len(ids)


def purge_notification_ledger(
    now=None, dry_run: bool = False, batch_size: int = 1000
) -> dict:
    """
    Remove ledger rows older than the retention windows.

    Returns how many rows were (or, with ``dry_run``, would be) removed per table. Attempts go
    first by their own, shorter window; removing a delivery also removes its remaining attempts.
    """
    now = now or timezone.now()
    windows = retention_windows()
    plan = []

    if windows["attempts"]:
        plan.append(
            (
                "attempts",
                NotificationAttempt.objects.filter(
                    created_at__lt=now - timedelta(days=windows["attempts"])
                ).exclude(outcome="started"),
            )
        )
    if windows["deliveries"]:
        plan.append(
            (
                "deliveries",
                NotificationDelivery.objects.filter(
                    status__in=DELIVERED_STATUSES,
                    created_at__lt=now - timedelta(days=windows["deliveries"]),
                ),
            )
        )
    if windows["failed"]:
        cutoff = now - timedelta(days=windows["failed"])
        plan.append(
            (
                "failed_deliveries",
                NotificationDelivery.objects.filter(
                    status="failed", updated_at__lt=cutoff
                ),
            )
        )
        plan.append(
            (
                "dead_letters",
                NotificationDeadLetter.objects.filter(failed_at__lt=cutoff),
            )
        )

    counts = {"attempts": 0, "deliveries": 0, "failed_deliveries": 0, "dead_letters": 0}
    for name, queryset in plan:
        counts[name] = (
            queryset.count() if dry_run else _delete_in_batches(queryset, batch_size)
        )

    if not dry_run and any(counts.values()):
        logger.info("Purged notification ledger: %s", counts)
    return counts
