"""Weekly email batching on the existing durable delivery ledger."""

from contextlib import AbstractContextManager
from datetime import datetime, timedelta
from datetime import timezone as datetime_timezone
from typing import Any, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import NotificationDelivery, NotificationPreference

MAX_PREVIEW_ITEMS = 100


def is_high_priority(meta):
    return str((meta or {}).get("priority", "")).strip().lower() in {
        "high",
        "urgent",
        "critical",
    }


def recipient_timezone(pref):
    profile = getattr(pref.user, "user_profile", None)
    try:
        return ZoneInfo(getattr(profile, "timezone", "UTC") or "UTC")
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return datetime_timezone.utc


def weekly_cutoff(pref, now):
    """Most recent Monday at the recipient's local digest time, including catch-up."""
    tz = recipient_timezone(pref)
    local = now.astimezone(tz)
    monday = local.date() - timedelta(days=local.weekday())
    cutoff = datetime.combine(monday, pref.digest_time, tzinfo=tz)
    if cutoff > local:
        cutoff = datetime.combine(
            monday - timedelta(days=7), pref.digest_time, tzinfo=tz
        )
    return cutoff


def cancel_disabled_weekly_deliveries(pref):
    """Opt-out cancels unsent weekly mail; it does not send a backlog immediately."""
    if pref.digest_frequency == "weekly" and pref.email_enabled:
        return
    NotificationDelivery.objects.filter(
        recipient=pref.user, claimed_at__isnull=True
    ).filter(
        Q(status="digest_pending")
        | Q(status="pending", meta__digest_frequency="weekly")
    ).update(
        status="cancelled",
        error_message="Weekly notification digest disabled before delivery",
        next_retry_at=None,
        updated_at=timezone.now(),
    )


def digest_delivery_allowed(delivery):
    if delivery.meta.get("digest_frequency") != "weekly":
        return True
    return (
        delivery.recipient.is_active
        and NotificationPreference.objects.filter(
            user=delivery.recipient, digest_frequency="weekly", email_enabled=True
        ).exists()
    )


def _dispatch_batch(delivery_id):
    # Import lazily: tasks calls queue_weekly_digest from its periodic scheduler.
    from .tasks import _enqueue, process_notification_delivery

    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        cast(Any, process_notification_delivery)(delivery_id)
    else:
        # Broker failures leave a pending, recoverable ledger entry.
        _enqueue(delivery_id)


def queue_weekly_digest(pref_id, now=None):
    """Snapshot a due weekly digest once, then hand it to the normal retry worker.

    The preference row serializes schedulers on PostgreSQL, while the delivery's
    unique dedupe key is a second guard. Source rows are linked and transitioned
    in the same transaction as the batch, so a crash cannot strand half a batch.
    """
    now = now or timezone.now()
    with cast(AbstractContextManager, transaction.atomic()):
        pref = (
            NotificationPreference.objects.select_for_update(of=("self",))
            .select_related("user", "user__user_profile")
            .get(pk=pref_id)
        )
        if (
            pref.digest_frequency != "weekly"
            or not pref.email_enabled
            or not pref.user.is_active
            or not pref.user.email
        ):
            cancel_disabled_weekly_deliveries(pref)
            return None
        cutoff = weekly_cutoff(pref, now)
        key = f"weekly-digest:{cutoff.date().isoformat()}"
        existing = NotificationDelivery.objects.filter(
            recipient=pref.user, channel="email", dedupe_key=key
        ).first()
        if existing is not None:
            return existing

        candidates = NotificationDelivery.objects.filter(
            recipient=pref.user,
            channel="email",
            status="digest_pending",
            created_at__lt=cutoff,
        )
        # Reading the in-app notification before batching suppresses its
        # deferred email. Null notification links still have a payload snapshot.
        candidates.filter(notification__is_read=True).update(
            status="cancelled",
            error_message="Read before weekly digest",
            updated_at=now,
        )
        if not candidates.exists():
            return None
        delivery, created = NotificationDelivery.objects.get_or_create(
            recipient=pref.user,
            channel="email",
            dedupe_key=key,
            defaults={
                "meta": {"digest_frequency": "weekly", "cutoff": cutoff.isoformat()},
            },
        )
        if not created:
            return delivery
        # Claim membership in one statement BEFORE rendering the snapshot. A late
        # commit with an old created_at must not be consumed by a later UPDATE
        # without appearing in the snapshot's count/preview.
        total = candidates.update(
            status="batched", digest_batch=delivery, updated_at=now
        )
        if not total:
            delivery.delete()
            return None
        grouped = {}
        for item in delivery.digest_items.order_by("created_at", "pk")[
            :MAX_PREVIEW_ITEMS
        ]:
            payload = item.payload
            kind = str(payload.get("notif_type", "notification"))
            grouped.setdefault(kind, []).append(
                {
                    "title": str(payload.get("title", ""))[:255],
                    "message": str(payload.get("message", ""))[:2000],
                    "created_at": item.created_at.isoformat(),
                }
            )
        delivery.payload = {
            "notif_type": "notification_digest",
            "title": "Your Weekly Notification Digest",
            "digest": {
                "grouped_notifications": grouped,
                "total_count": total,
                "omitted_count": max(0, total - MAX_PREVIEW_ITEMS),
            },
        }
        delivery.save(update_fields=["payload"])
        transaction.on_commit(lambda: _dispatch_batch(delivery.pk))
        return delivery
