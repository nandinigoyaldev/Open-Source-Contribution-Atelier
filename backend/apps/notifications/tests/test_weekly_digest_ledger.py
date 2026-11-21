"""Durable weekly batch membership, schedule boundaries and transaction safety."""

import datetime as dt
from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractContextManager
from threading import Barrier
from typing import cast

import pytest
from django.db import close_old_connections, connection, connections, transaction
from django.db.models import QuerySet

from apps.notifications import digests
from apps.notifications.digests import queue_weekly_digest, weekly_cutoff
from apps.notifications.models import Notification, NotificationDelivery
from apps.notifications.retention import purge_notification_ledger

pytestmark = pytest.mark.django_db
UTC = dt.timezone.utc
MONDAY = dt.datetime(2026, 11, 9, 8, tzinfo=UTC)


@pytest.fixture(autouse=True)
def hold_queue(monkeypatch):
    # The delivery adapter is integrated in the next layer; test durable queue state here.
    monkeypatch.setattr(digests, "_dispatch_batch", lambda _: None)


def notify(pref, title="Ordinary"):
    notification = Notification.objects.create(
        recipient=pref.user, notif_type="badge", title=title
    )
    return NotificationDelivery.objects.create(
        recipient=pref.user,
        notification=notification,
        channel="email",
        status="digest_pending",
        payload={"notif_type": "badge", "title": title, "message": "Message"},
    )


@pytest.mark.parametrize(
    "zone,now,expected",
    [
        (
            "Asia/Kolkata",
            dt.datetime(2026, 11, 9, 3, tzinfo=UTC),
            dt.datetime(2026, 11, 9, 2, 30, tzinfo=UTC),
        ),
        (
            "America/New_York",
            dt.datetime(2026, 11, 2, 13, tzinfo=UTC),
            dt.datetime(2026, 11, 2, 13, tzinfo=UTC),
        ),
        (
            "America/New_York",
            dt.datetime(2026, 11, 2, 12, 59, tzinfo=UTC),
            dt.datetime(2026, 10, 26, 12, tzinfo=UTC),
        ),
        ("Not/A-Timezone", MONDAY, MONDAY),
    ],
)
def test_local_time_dst_and_invalid_zone_fallback(
    digest_subscriber, zone, now, expected
):
    profile = digest_subscriber.user.user_profile
    profile.timezone = zone
    profile.save(update_fields=["timezone"])
    assert weekly_cutoff(digest_subscriber, now) == expected


def test_read_items_are_not_repeated_in_digest(
    digest_subscriber, digest_clock, digest_batch, mailoutbox
):
    row = notify(digest_subscriber)
    Notification.objects.filter(pk=row.notification_id).update(is_read=True)
    digest_clock.now = MONDAY
    assert digest_batch() is None
    row.refresh_from_db()
    assert row.status == "cancelled"
    assert len(mailoutbox) == 0


def test_outer_transaction_rollback_does_not_queue_or_consume_items(
    digest_subscriber, digest_clock, digest_batch, mailoutbox
):
    source = notify(digest_subscriber)
    digest_clock.now = MONDAY
    with (
        pytest.raises(RuntimeError),
        cast(AbstractContextManager, transaction.atomic()),
    ):
        queue_weekly_digest(digest_subscriber.pk, digest_clock.now)
        raise RuntimeError("transaction rolled back")
    source.refresh_from_db()
    assert source.status == "digest_pending"
    assert source.digest_batch_id is None
    assert len(mailoutbox) == 0
    assert not NotificationDelivery.objects.filter(
        dedupe_key__startswith="weekly-digest:"
    ).exists()


def test_retention_keeps_pending_items_but_purges_old_terminal_states(
    digest_subscriber, digest_clock
):
    for status in ["digest_pending", "batched", "cancelled"]:
        NotificationDelivery.objects.create(
            recipient=digest_subscriber.user, channel="email", status=status
        )
    digest_clock.now += dt.timedelta(days=100)
    purge_notification_ledger(now=digest_clock.now)
    assert list(NotificationDelivery.objects.values_list("status", flat=True)) == [
        "digest_pending"
    ]


@pytest.mark.skipif(
    connection.vendor != "postgresql", reason="Requires real PostgreSQL row locks"
)
@pytest.mark.django_db(transaction=True)
def test_concurrent_postgres_schedulers_queue_one_batch(
    digest_subscriber, digest_clock, monkeypatch
):
    from apps.notifications import digests

    source = notify(digest_subscriber)
    digest_clock.now = MONDAY
    scheduled = []
    monkeypatch.setattr(digests, "_dispatch_batch", scheduled.append)
    barrier = Barrier(2)
    pref_id = digest_subscriber.pk

    def worker():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            row = queue_weekly_digest(pref_id, MONDAY)
            assert row is not None
            return row.pk
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker) for _ in range(2)]
        ids = [future.result(timeout=20) for future in futures]
    source.refresh_from_db()
    assert ids[0] == ids[1] == source.digest_batch_id
    assert scheduled == [ids[0]]
    assert (
        NotificationDelivery.objects.filter(
            dedupe_key__startswith="weekly-digest:"
        ).count()
        == 1
    )


def test_late_old_item_is_not_consumed_without_entering_snapshot(
    digest_subscriber, digest_clock, digest_batch, monkeypatch
):
    notify(digest_subscriber, "Original")
    digest_clock.now = MONDAY
    original_update = QuerySet.update
    late_items = []

    def update_then_late_commit(queryset, **kwargs):
        count = original_update(queryset, **kwargs)
        if (
            queryset.model is NotificationDelivery
            and kwargs.get("status") == "batched"
            and not late_items
        ):
            late = NotificationDelivery.objects.create(
                recipient=digest_subscriber.user,
                channel="email",
                status="digest_pending",
                payload={"title": "Late old item"},
            )
            original_update(
                NotificationDelivery.objects.filter(pk=late.pk),
                created_at=MONDAY - dt.timedelta(days=1),
            )
            late_items.append(late)
        return count

    monkeypatch.setattr(QuerySet, "update", update_then_late_commit)
    row = digest_batch()
    assert row.payload["digest"]["total_count"] == row.digest_items.count() == 1
    late_items[0].refresh_from_db()
    assert late_items[0].status == "digest_pending"
    assert late_items[0].digest_batch_id is None
