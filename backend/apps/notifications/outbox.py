"""
Transactional outbox for notifications.

Notifying straight from the code that changes data has two failure modes: the notification goes
out and then the transaction rolls back (a notification about something that never happened), or
the transaction commits and the process dies before anything was queued (a change nobody hears
about). The outbox removes both:

1. ``enqueue_notification`` writes a ``NotificationOutbox`` row *inside the caller's transaction*.
   Roll back and the row is gone with the change; commit and the row is durable.
2. A dispatcher (``dispatch_due`` / the ``dispatch_notification_outbox`` task and command) claims
   due rows, hands each one to ``dispatch_notification`` (which writes the ``Notification`` and the
   ``NotificationDelivery`` rows of the delivery ledger) and marks the row ``dispatched`` in the
   same transaction. Channel delivery, retries and dead letters per channel stay in the ledger.

Claiming is a short transaction using ``select_for_update(skip_locked=True)`` so concurrent
workers never take the same row, plus a lease (``locked_at``) so a row held by a dead worker is
picked up again. Every claim counts as an attempt, so a row that keeps killing its worker still
ends up dead. A failed hand-off is retried with exponential backoff and dead-lettered after
``NOTIFICATION_OUTBOX_MAX_ATTEMPTS`` tries or on a permanent error.

The delivery key of the ledger is the outbox ``idempotency_key``, which makes the hand-off safe to
repeat: a worker that dies right after writing the deliveries cannot cause a second notification.
"""

import logging
import uuid
from datetime import timedelta
from typing import List, Optional

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Count, Exists, F, Min, OuterRef, Q
from django.utils import timezone

from apps.notifications.delivery import (
    MAX_ERROR_CHARS,
    PERMANENT,
    TRANSIENT,
    backoff_seconds,
    classify_failure,
    truncate,
)
from apps.notifications.models import (
    NotificationDeadLetter,
    NotificationDelivery,
    NotificationOutbox,
)

logger = logging.getLogger(__name__)

PENDING = "pending"
PROCESSING = "processing"
DISPATCHED = "dispatched"
DEAD = "dead"
STATUSES = (PENDING, PROCESSING, DISPATCHED, DEAD)

# What ``process_row`` reports besides the final statuses above.
RETRY = "retry"
LOST = "lost"


def _setting(name, default):
    return getattr(settings, name, default)


def max_attempts() -> int:
    """Hand-off tries (claims) a row gets before it is dead-lettered."""
    return max(1, int(_setting("NOTIFICATION_OUTBOX_MAX_ATTEMPTS", 5)))


def lease() -> timedelta:
    """How long a worker may hold a row before another worker may take it over."""
    return timedelta(seconds=int(_setting("NOTIFICATION_OUTBOX_LEASE_SECONDS", 120)))


def batch_size() -> int:
    return max(1, int(_setting("NOTIFICATION_OUTBOX_BATCH_SIZE", 100)))


def retry_delay(attempt: int) -> int:
    base = int(_setting("NOTIFICATION_OUTBOX_BACKOFF_SECONDS", 30))
    return backoff_seconds(attempt, base=base, cap=3600)


class _ClaimLost(Exception):
    """The row is no longer ours (lease expired and another worker took it)."""


# --------------------------------------------------------------------------- #
# Producer side                                                               #
# --------------------------------------------------------------------------- #


def enqueue_notification(
    recipient,
    notif_type: str,
    title: str,
    message: str,
    meta: Optional[dict] = None,
    sender=None,
    idempotency_key: Optional[str] = None,
    source: str = "",
    kick: bool = True,
) -> NotificationOutbox:
    """
    Record the intent to notify ``recipient``. Call it in the same ``transaction.atomic()`` block
    as the change the notification is about::

        with transaction.atomic():
            badge = UserBadge.objects.create(user=user, badge=badge)
            enqueue_notification(
                user, "badge", "New badge", f"You earned {badge.badge.name}",
                idempotency_key=make_dedupe_key("badge", user.id, badge.badge_id),
                source=f"progress.UserBadge:{badge.pk}",
            )

    Nothing is sent here. After the transaction commits a dispatcher task is queued as a fast
    path; if that fails (broker down, process killed) the periodic dispatcher still finds the row.

    ``idempotency_key`` makes the call idempotent per recipient: the same key again returns the
    existing row. Without one every call is a new notification.
    """
    key = str(idempotency_key)[:128] if idempotency_key else uuid.uuid4().hex
    fields = {
        "sender": sender,
        "notif_type": notif_type,
        "title": title,
        "message": message,
        "meta": meta or {},
        "source": str(source)[:255],
    }
    try:
        # A savepoint, so a duplicate key does not poison the caller's transaction.
        with transaction.atomic():
            row = NotificationOutbox.objects.create(
                recipient=recipient, idempotency_key=key, **fields
            )
    except IntegrityError:
        existing = NotificationOutbox.objects.filter(
            recipient=recipient, idempotency_key=key
        ).first()
        if existing is None:
            raise
        return existing

    if kick:
        transaction.on_commit(lambda: _kick(row.pk))
    return row


def _kick(row_id: int) -> None:
    """Best effort: ask a worker to dispatch the row now instead of at the next sweep."""
    try:
        from apps.notifications.tasks import dispatch_outbox_row

        dispatch_outbox_row.delay(row_id)  # type: ignore[attr-defined]
    except Exception as exc:
        logger.warning(
            "Could not queue outbox row #%s, the sweep will pick it up: %s",
            row_id,
            exc,
        )


# --------------------------------------------------------------------------- #
# Dispatcher                                                                  #
# --------------------------------------------------------------------------- #


def _claimable(now) -> Q:
    return Q(status=PENDING, next_attempt_at__lte=now) | Q(
        status=PROCESSING, locked_at__lt=now - lease()
    )


def claim_rows(
    limit: Optional[int] = None, now=None, only_id: Optional[int] = None
) -> List[NotificationOutbox]:
    """
    Take up to ``limit`` due rows for this worker and return them.

    Due means ``pending`` with ``next_attempt_at`` in the past, or ``processing`` with an expired
    lease. The rows are locked with ``SELECT ... FOR UPDATE SKIP LOCKED`` (PostgreSQL, MySQL 8)
    so two claimers never wait for or take the same row; the following ``UPDATE`` repeats the
    due condition, so the claim is still exclusive on a database without row locks (SQLite).
    """
    now = now or timezone.now()
    limit = limit or batch_size()
    token = uuid.uuid4().hex
    due = _claimable(now)
    with transaction.atomic():
        candidates = NotificationOutbox.objects.select_for_update(
            skip_locked=True
        ).filter(due)
        if only_id is not None:
            candidates = candidates.filter(pk=only_id)
        ids = list(
            candidates.order_by("next_attempt_at", "id").values_list("pk", flat=True)[
                :limit
            ]
        )
        if not ids:
            return []
        NotificationOutbox.objects.filter(pk__in=ids).filter(due).update(
            status=PROCESSING,
            locked_at=now,
            locked_by=token,
            attempts=F("attempts") + 1,
            updated_at=now,
        )
    return list(
        NotificationOutbox.objects.filter(pk__in=ids, locked_by=token)
        .select_related("recipient", "sender")
        .order_by("next_attempt_at", "id")
    )


def process_row(row: NotificationOutbox) -> str:
    """
    Hand one claimed row to the delivery ledger and say how it went: ``dispatched``, ``retry``,
    ``dead`` or ``lost`` (another worker owns it now; nothing was changed).
    """
    from apps.notifications.tasks import dispatch_notification, start_deliveries

    if row.attempts > max_attempts():
        # Claimed again and again without ever finishing: its workers keep dying.
        _give_up(row, "Gave up after repeated worker failures", TRANSIENT)
        return DEAD

    try:
        with transaction.atomic():
            deliveries = dispatch_notification(
                row.recipient,
                row.notif_type,
                row.title,
                row.message,
                meta=row.meta,
                sender=row.sender,
                dedupe_key=row.idempotency_key,
                deliver=False,
            )
            now = timezone.now()
            done = NotificationOutbox.objects.filter(
                pk=row.pk, status=PROCESSING, locked_by=row.locked_by
            ).update(
                status=DISPATCHED,
                dispatched_at=now,
                locked_at=None,
                locked_by="",
                error_class="",
                last_error="",
                updated_at=now,
            )
            if not done:
                raise _ClaimLost()
    except _ClaimLost:
        logger.info("Outbox row #%s was taken over by another worker.", row.pk)
        return LOST
    except Exception as exc:
        return _record_failure(row, exc)

    # The deliveries are committed from here on; a failure to start them is the ledger's job
    # (``recover_stale_deliveries`` queues pending deliveries nobody picked up).
    try:
        start_deliveries(deliveries)
    except Exception as exc:
        logger.warning(
            "Outbox row #%s dispatched but starting its deliveries failed: %s",
            row.pk,
            exc,
        )
    return DISPATCHED


def _record_failure(row: NotificationOutbox, exc: BaseException) -> str:
    kind = classify_failure(exc)
    error = truncate(f"{exc.__class__.__name__}: {exc}", MAX_ERROR_CHARS)
    if kind == PERMANENT or row.attempts >= max_attempts():
        return _give_up(row, error, kind)

    now = timezone.now()
    updated = NotificationOutbox.objects.filter(
        pk=row.pk, status=PROCESSING, locked_by=row.locked_by
    ).update(
        status=PENDING,
        next_attempt_at=now + timedelta(seconds=retry_delay(row.attempts)),
        locked_at=None,
        locked_by="",
        error_class=kind,
        last_error=error,
        updated_at=now,
    )
    logger.warning(
        "Outbox row #%s failed (attempt %s of %s), will retry: %s",
        row.pk,
        row.attempts,
        max_attempts(),
        error,
    )
    return RETRY if updated else LOST


def _give_up(row: NotificationOutbox, error: str, kind: str) -> str:
    """Move the row to ``dead`` and leave a ``NotificationDeadLetter`` for the existing tooling."""
    now = timezone.now()
    with transaction.atomic():
        updated = NotificationOutbox.objects.filter(
            pk=row.pk, status=PROCESSING, locked_by=row.locked_by
        ).update(
            status=DEAD,
            dead_at=now,
            locked_at=None,
            locked_by="",
            error_class=kind,
            last_error=truncate(error, MAX_ERROR_CHARS),
            updated_at=now,
        )
        if not updated:
            return LOST
        NotificationDeadLetter.objects.create(
            recipient_id=row.recipient_id,
            channel="outbox",
            retry_count=row.attempts,
            error_message=truncate(error, MAX_ERROR_CHARS),
            payload={
                "outbox_id": row.pk,
                "idempotency_key": row.idempotency_key,
                "source": row.source,
                "notif_type": row.notif_type,
                "title": row.title,
                "message": row.message,
                "meta": row.meta,
            },
        )
    logger.error(
        "Outbox row #%s is dead after %s attempts: %s", row.pk, row.attempts, error
    )
    return DEAD


def dispatch_due(limit: Optional[int] = None, now=None, max_rows: int = 500) -> dict:
    """
    Claim and process due rows, a batch at a time, until none are left or ``max_rows`` were
    handled. Returns a count per outcome, e.g. ``{"claimed": 3, "dispatched": 2, "retry": 1}``.
    """
    summary = {"claimed": 0, DISPATCHED: 0, RETRY: 0, DEAD: 0, LOST: 0}
    limit = limit or batch_size()
    while summary["claimed"] < max_rows:
        rows = claim_rows(limit=min(limit, max_rows - summary["claimed"]), now=now)
        if not rows:
            break
        for row in rows:
            summary["claimed"] += 1
            summary[process_row(row)] += 1
        if len(rows) < limit:
            break
    return summary


def dispatch_one(row_id: int) -> dict:
    """The fast path after commit: process just this row if it is due."""
    summary = {"claimed": 0, DISPATCHED: 0, RETRY: 0, DEAD: 0, LOST: 0}
    for row in claim_rows(limit=1, only_id=row_id):
        summary["claimed"] += 1
        summary[process_row(row)] += 1
    return summary


# --------------------------------------------------------------------------- #
# Metrics and reconciliation                                                  #
# --------------------------------------------------------------------------- #


def outbox_stats(now=None) -> dict:
    """
    Counts per status and the ages that matter, in one query.

    * ``backlog`` is the rows not yet handed to the ledger (``pending`` + ``processing``);
      ``oldest_backlog_age_seconds`` is the age of the oldest of them (``None`` when empty).
    * ``overdue`` is the part of the backlog that is due now, which is what a healthy dispatcher
      keeps close to zero (a row waiting out its retry backoff is backlog but not overdue).
    * ``stale_processing`` are rows whose lease has expired (a worker died holding them).
    * ``dead`` are the permanently failed rows; ``oldest_dead_age_seconds`` is how long the
      oldest one has been waiting for somebody to look at it.
    """
    now = now or timezone.now()
    backlog = Q(status__in=(PENDING, PROCESSING))
    agg = NotificationOutbox.objects.aggregate(
        pending=Count("pk", filter=Q(status=PENDING)),
        processing=Count("pk", filter=Q(status=PROCESSING)),
        dispatched=Count("pk", filter=Q(status=DISPATCHED)),
        dead=Count("pk", filter=Q(status=DEAD)),
        overdue=Count(
            "pk",
            filter=Q(status=PENDING, next_attempt_at__lte=now)
            | Q(status=PROCESSING, locked_at__lt=now - lease()),
        ),
        stale_processing=Count(
            "pk", filter=Q(status=PROCESSING, locked_at__lt=now - lease())
        ),
        oldest_backlog=Min("created_at", filter=backlog),
        oldest_dead=Min("dead_at", filter=Q(status=DEAD)),
    )
    oldest_backlog = agg.pop("oldest_backlog")
    oldest_dead = agg.pop("oldest_dead")
    agg["backlog"] = agg["pending"] + agg["processing"]
    agg["oldest_backlog_age_seconds"] = (
        max(0.0, (now - oldest_backlog).total_seconds()) if oldest_backlog else None
    )
    agg["oldest_dead_age_seconds"] = (
        max(0.0, (now - oldest_dead).total_seconds()) if oldest_dead else None
    )
    return agg


def reconcile(now=None, since_days: int = 7, dead_limit: int = 20) -> dict:
    """
    Everything an operator needs to see whether the outbox and the ledger agree.

    Besides ``outbox_stats`` this lists the permanently failed rows (``dead_rows``) and counts
    rows that were dispatched in the last ``since_days`` days but whose ledger deliveries failed
    (``dispatched_with_failed_deliveries``): the hand-off worked, a channel gave up.
    """
    now = now or timezone.now()
    report = outbox_stats(now)
    report["dead_rows"] = list(
        NotificationOutbox.objects.filter(status=DEAD)
        .order_by("dead_at", "id")
        .values(
            "id",
            "recipient_id",
            "notif_type",
            "source",
            "attempts",
            "error_class",
            "last_error",
            "dead_at",
        )[:dead_limit]
    )
    failed = NotificationDelivery.objects.filter(
        recipient_id=OuterRef("recipient_id"),
        dedupe_key=OuterRef("idempotency_key"),
        status="failed",
    )
    report["dispatched_with_failed_deliveries"] = (
        NotificationOutbox.objects.filter(
            status=DISPATCHED, dispatched_at__gte=now - timedelta(days=since_days)
        )
        .filter(Exists(failed))
        .count()
    )
    return report


def requeue_dead(row_ids=None) -> int:
    """
    Give dead rows a fresh set of attempts (after the cause was fixed). Returns how many were
    reset. The ``NotificationDeadLetter`` written when the row died is left as the history.
    """
    qs = NotificationOutbox.objects.filter(status=DEAD)
    if row_ids:
        qs = qs.filter(pk__in=row_ids)
    now = timezone.now()
    return qs.update(
        status=PENDING,
        attempts=0,
        next_attempt_at=now,
        dead_at=None,
        locked_at=None,
        locked_by="",
        updated_at=now,
    )


def purge_dispatched(now=None, batch: int = 1000) -> int:
    """Delete dispatched rows older than ``NOTIFICATION_DELIVERY_RETENTION_DAYS`` (0 keeps them)."""
    days = int(_setting("NOTIFICATION_DELIVERY_RETENTION_DAYS", 90))
    if days <= 0:
        return 0
    now = now or timezone.now()
    cutoff = now - timedelta(days=days)
    deleted = 0
    while True:
        ids = list(
            NotificationOutbox.objects.filter(
                status=DISPATCHED, dispatched_at__lt=cutoff
            ).values_list("pk", flat=True)[:batch]
        )
        if not ids:
            return deleted
        NotificationOutbox.objects.filter(pk__in=ids).delete()
        deleted += len(ids)
