# pyright: reportAttributeAccessIssue=false, reportIndexIssue=false, reportOperatorIssue=false, reportArgumentType=false, reportReturnType=false, reportGeneralTypeIssues=false, reportCallIssue=false
"""Transactional notification outbox: atomic enqueue, claiming, retries, dead letters, metrics (#3320)."""

import json
from datetime import timedelta
from io import StringIO
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import transaction
from django.db.models.query import QuerySet
from django.utils import timezone

from apps.notifications import metrics, outbox, tasks
from apps.notifications.delivery import make_dedupe_key
from apps.notifications.models import (
    Notification,
    NotificationDeadLetter,
    NotificationDelivery,
    NotificationOutbox,
    NotificationPreference,
)
from apps.notifications.outbox import (
    DEAD,
    DISPATCHED,
    LOST,
    PENDING,
    PROCESSING,
    RETRY,
    claim_rows,
    dispatch_due,
    enqueue_notification,
    outbox_stats,
    process_row,
    reconcile,
    requeue_dead,
)

WEBHOOK_DELIVER = "apps.notifications.channels.webhook_channel.WebhookChannel.deliver"
Preferences: Any = NotificationPreference
_dispatch_row_task: Any = tasks.dispatch_outbox_row
_sweep_task: Any = tasks.dispatch_notification_outbox


@pytest.fixture(autouse=True)
def outbox_settings(settings, db):
    from django.core.cache import cache

    cache.clear()
    settings.NOTIFICATION_OUTBOX_MAX_ATTEMPTS = 3
    settings.NOTIFICATION_OUTBOX_LEASE_SECONDS = 120
    settings.NOTIFICATION_OUTBOX_BACKOFF_SECONDS = 30
    settings.NOTIFICATION_OUTBOX_BATCH_SIZE = 100
    settings.NOTIFICATION_MAX_ATTEMPTS = 3


@pytest.fixture
def prefs(user):
    pref, _ = Preferences.objects.get_or_create(user=user)
    pref.channel_preferences = {"badge": {"in_app": True, "webhook": True}}
    pref.save()
    return pref


@pytest.fixture
def no_kick(monkeypatch):
    """Do not run the after-commit fast path; tests drive the dispatcher themselves."""
    kick = MagicMock()
    monkeypatch.setattr(outbox, "_kick", kick)
    return kick


def enqueue(user, key="k1", **kwargs):
    return enqueue_notification(
        user, "badge", "New badge", "You earned it", idempotency_key=key, **kwargs
    )


def ago(seconds):
    return timezone.now() - timedelta(seconds=seconds)


class Boom(Exception):
    pass


def failing_dispatch(exc):
    return patch.object(
        tasks, "dispatch_notification", side_effect=exc
    )  # tasks.dispatch_notification is imported lazily by outbox.process_row


# --------------------------------------------------------------------------- #
# Atomicity with the source event                                             #
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestAtomicEnqueue:
    def test_a_rollback_leaves_no_intent_and_queues_nothing(
        self, user, django_capture_on_commit_callbacks, no_kick
    ):
        with django_capture_on_commit_callbacks(execute=True) as callbacks:
            with pytest.raises(Boom):
                with transaction.atomic():
                    Notification.objects.create(
                        recipient=user, notif_type="badge", title="source", message="m"
                    )  # stands in for the domain change
                    enqueue(user)
                    raise Boom()
        assert NotificationOutbox.objects.count() == 0
        assert Notification.objects.count() == 0
        assert callbacks == []
        no_kick.assert_not_called()

    def test_a_commit_keeps_the_intent_and_queues_it_only_after_the_commit(
        self, user, django_capture_on_commit_callbacks, no_kick
    ):
        with django_capture_on_commit_callbacks(execute=False) as callbacks:
            with transaction.atomic():
                row = enqueue(user)
                no_kick.assert_not_called()  # nothing may run before the commit
        assert len(callbacks) == 1
        assert NotificationOutbox.objects.get().pk == row.pk
        assert row.status == PENDING and row.attempts == 0
        # nothing was notified yet: the intent is only recorded
        assert Notification.objects.count() == 0
        for callback in callbacks:
            callback()
        no_kick.assert_called_once_with(row.pk)

    def test_a_savepoint_rollback_inside_the_transaction_drops_only_its_own_intent(
        self, user, no_kick
    ):
        with transaction.atomic():
            keep = enqueue(user, key="keep")
            with pytest.raises(Boom):
                with transaction.atomic():
                    enqueue(user, key="drop")
                    raise Boom()
        assert list(NotificationOutbox.objects.values_list("pk", flat=True)) == [
            keep.pk
        ]

    def test_a_committed_intent_survives_a_broken_broker_and_the_sweep_delivers_it(
        self, user, prefs, django_capture_on_commit_callbacks
    ):
        with patch.object(
            tasks.dispatch_outbox_row, "delay", side_effect=ConnectionError("no broker")
        ):
            with django_capture_on_commit_callbacks(execute=True):
                with transaction.atomic():
                    enqueue(user)
        row = NotificationOutbox.objects.get()
        assert row.status == PENDING  # the enqueue did not fail, the row is still there

        with patch(WEBHOOK_DELIVER, return_value=True):
            summary = dispatch_due()
        row.refresh_from_db()
        assert summary[DISPATCHED] == 1 and row.status == DISPATCHED
        assert Notification.objects.filter(recipient=user).count() == 1

    def test_the_fast_path_after_commit_dispatches_the_row(
        self, user, prefs, django_capture_on_commit_callbacks
    ):
        # run the queued task inline, as an eager worker would (no broker in tests)
        with (
            patch.object(
                tasks.dispatch_outbox_row,
                "delay",
                side_effect=lambda row_id: _dispatch_row_task(row_id),
            ),
            patch(WEBHOOK_DELIVER, return_value=True) as webhook,
        ):
            with django_capture_on_commit_callbacks(execute=True):
                with transaction.atomic():
                    enqueue(user)
        assert NotificationOutbox.objects.get().status == DISPATCHED
        assert webhook.call_count == 1

    def test_a_non_serializable_payload_fails_in_the_callers_transaction(self, user):
        with pytest.raises(TypeError):
            with transaction.atomic():
                enqueue_notification(
                    user, "badge", "T", "M", meta={"x": object()}, idempotency_key="k"
                )
        assert NotificationOutbox.objects.count() == 0


@pytest.mark.django_db
class TestIdempotentEnqueue:
    def test_the_same_key_for_the_same_user_is_one_row(
        self, user, no_kick, django_capture_on_commit_callbacks
    ):
        with django_capture_on_commit_callbacks(execute=True):
            first = enqueue(user, key="same")
            second = enqueue(user, key="same")
        assert first.pk == second.pk
        assert NotificationOutbox.objects.count() == 1
        no_kick.assert_called_once()  # the duplicate does not queue a second task

    def test_a_duplicate_does_not_break_the_callers_transaction(self, user, no_kick):
        with transaction.atomic():
            enqueue(user, key="same")
            enqueue(user, key="same")
            Notification.objects.create(
                recipient=user, notif_type="badge", title="after", message="m"
            )
        assert Notification.objects.count() == 1

    def test_other_keys_and_other_users_are_separate_rows(
        self, user, django_user_model, no_kick
    ):
        other = django_user_model.objects.create_user(
            username="other", email="o@example.com", password="x"
        )
        enqueue(user, key="a")
        enqueue(user, key="b")
        enqueue(other, key="a")
        enqueue_notification(user, "badge", "T", "M")  # no key: always new
        enqueue_notification(user, "badge", "T", "M")
        assert NotificationOutbox.objects.count() == 5

    def test_the_key_and_source_are_stored(self, user, no_kick):
        row = enqueue(user, key=make_dedupe_key("badge", user.id, 7), source="x:1")
        assert row.idempotency_key == make_dedupe_key("badge", user.id, 7)
        assert row.source == "x:1"


# --------------------------------------------------------------------------- #
# Dispatching into the delivery ledger                                        #
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestDispatch:
    def test_a_row_becomes_a_notification_and_ledger_deliveries(
        self, user, prefs, no_kick
    ):
        row = enqueue(user, meta={"badge_id": 3}, source="progress.UserBadge:3")
        with patch(WEBHOOK_DELIVER, return_value=True) as webhook:
            summary = dispatch_due()

        row.refresh_from_db()
        assert summary == {
            "claimed": 1,
            DISPATCHED: 1,
            RETRY: 0,
            DEAD: 0,
            LOST: 0,
        }
        assert row.status == DISPATCHED and row.dispatched_at
        assert row.attempts == 1 and row.locked_by == "" and row.locked_at is None
        notification = Notification.objects.get(recipient=user)
        assert notification.title == "New badge" and notification.meta == {
            "badge_id": 3
        }
        deliveries = NotificationDelivery.objects.filter(recipient=user)
        assert {d.channel for d in deliveries} == {"in_app", "webhook"}
        assert {d.dedupe_key for d in deliveries} == {row.idempotency_key}
        assert {d.status for d in deliveries} == {"sent"}
        assert webhook.call_count == 1

    def test_the_sender_is_carried_over(self, user, django_user_model, prefs, no_kick):
        sender = django_user_model.objects.create_user(
            username="sender", email="s@example.com", password="x"
        )
        enqueue(user, sender=sender)
        with patch(WEBHOOK_DELIVER, return_value=True):
            dispatch_due()
        assert Notification.objects.get().sender == sender

    def test_a_dispatched_row_is_not_dispatched_again(self, user, prefs, no_kick):
        enqueue(user)
        with patch(WEBHOOK_DELIVER, return_value=True) as webhook:
            dispatch_due()
            second = dispatch_due()
        assert second["claimed"] == 0
        assert Notification.objects.count() == 1 and webhook.call_count == 1

    def test_a_crash_after_the_hand_off_cannot_notify_twice(self, user, prefs, no_kick):
        row = enqueue(user)
        with patch(WEBHOOK_DELIVER, return_value=True) as webhook:
            dispatch_due()
            # the worker died after the deliveries were written but before the row said so
            NotificationOutbox.objects.filter(pk=row.pk).update(
                status=PROCESSING, locked_at=ago(600), locked_by="dead-worker"
            )
            summary = dispatch_due()
        row.refresh_from_db()
        assert summary[DISPATCHED] == 1 and row.status == DISPATCHED
        assert Notification.objects.count() == 1
        assert NotificationDelivery.objects.count() == 2
        assert webhook.call_count == 1

    def test_the_channels_are_not_touched_inside_the_hand_off_transaction(
        self, user, prefs, no_kick
    ):
        enqueue(user)
        seen = {}

        def deliver(*args, **kwargs):
            seen["row_status"] = NotificationOutbox.objects.get().status
            return True

        with patch(WEBHOOK_DELIVER, side_effect=deliver):
            dispatch_due()
        # by the time a channel is called, the row is already committed as dispatched
        assert seen["row_status"] == DISPATCHED

    def test_a_user_with_every_channel_off_is_still_dispatched(self, user, no_kick):
        pref, _ = Preferences.objects.get_or_create(user=user)
        pref.channel_preferences = {"badge": {"in_app": False}}
        pref.save()
        row = enqueue(user)
        assert dispatch_due()[DISPATCHED] == 1
        row.refresh_from_db()
        assert row.status == DISPATCHED
        assert NotificationDelivery.objects.count() == 0

    def test_a_failing_channel_is_the_ledgers_business_not_the_outboxs(
        self, user, prefs, no_kick
    ):
        row = enqueue(user)
        with patch(WEBHOOK_DELIVER, return_value=False):
            dispatch_due()
        row.refresh_from_db()
        assert row.status == DISPATCHED
        webhook = NotificationDelivery.objects.get(channel="webhook")
        assert webhook.status == "pending" and webhook.retry_count == 1

    def test_the_celery_tasks_run_the_dispatcher(self, user, prefs, no_kick):
        first = enqueue(user, key="a")
        enqueue(user, key="b")
        with patch(WEBHOOK_DELIVER, return_value=True):
            assert _dispatch_row_task(first.pk)[DISPATCHED] == 1
            assert _sweep_task()[DISPATCHED] == 1
        assert not NotificationOutbox.objects.exclude(status=DISPATCHED).exists()

    def test_the_fast_path_ignores_a_row_that_is_not_due(self, user, prefs, no_kick):
        row = enqueue(user)
        NotificationOutbox.objects.filter(pk=row.pk).update(
            next_attempt_at=timezone.now() + timedelta(minutes=5)
        )
        assert _dispatch_row_task(row.pk)["claimed"] == 0


# --------------------------------------------------------------------------- #
# Claiming                                                                    #
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestClaiming:
    def test_a_claim_is_exclusive_while_the_lease_holds(self, user, no_kick):
        enqueue(user)
        first = claim_rows()
        assert len(first) == 1 and first[0].status == PROCESSING
        assert first[0].attempts == 1 and first[0].locked_by
        assert claim_rows() == []  # the second worker gets nothing

    def test_two_workers_split_the_rows_between_them(self, user, no_kick):
        for i in range(5):
            enqueue(user, key=f"k{i}")
        first = claim_rows(limit=3)
        second = claim_rows(limit=3)
        assert len(first) == 3 and len(second) == 2
        assert not {r.pk for r in first} & {r.pk for r in second}

    def test_rows_are_claimed_oldest_due_first_and_only_when_due(self, user, no_kick):
        later = enqueue(user, key="later")
        sooner = enqueue(user, key="sooner")
        future = enqueue(user, key="future")
        NotificationOutbox.objects.filter(pk=later.pk).update(next_attempt_at=ago(10))
        NotificationOutbox.objects.filter(pk=sooner.pk).update(next_attempt_at=ago(60))
        NotificationOutbox.objects.filter(pk=future.pk).update(
            next_attempt_at=timezone.now() + timedelta(hours=1)
        )
        assert [r.pk for r in claim_rows()] == [sooner.pk, later.pk]

    def test_an_expired_lease_lets_another_worker_take_over(self, user, no_kick):
        row = enqueue(user)
        claim_rows()
        assert claim_rows() == []
        NotificationOutbox.objects.filter(pk=row.pk).update(locked_at=ago(121))
        retaken = claim_rows()
        assert [r.pk for r in retaken] == [row.pk]
        assert retaken[0].attempts == 2  # the dead worker's try counts

    def test_the_claim_locks_rows_with_skip_locked(self, user, no_kick):
        enqueue(user)
        real = QuerySet.select_for_update
        with patch.object(
            QuerySet, "select_for_update", autospec=True, side_effect=real
        ) as spy:
            claim_rows()
        assert spy.call_count == 1
        assert spy.call_args.kwargs == {"skip_locked": True}

    def test_a_worker_that_lost_its_lease_changes_nothing(self, user, prefs, no_kick):
        row = enqueue(user)
        stale = claim_rows()[0]
        NotificationOutbox.objects.filter(pk=row.pk).update(locked_at=ago(500))
        fresh = claim_rows()[0]
        assert stale.locked_by != fresh.locked_by

        # the slow worker wakes up after the takeover: its work is rolled back
        with patch(WEBHOOK_DELIVER, return_value=True):
            assert process_row(stale) == LOST
        assert Notification.objects.count() == 0
        assert NotificationDelivery.objects.count() == 0
        assert NotificationOutbox.objects.get().status == PROCESSING

        with patch(WEBHOOK_DELIVER, return_value=True):
            assert process_row(fresh) == DISPATCHED
        assert Notification.objects.count() == 1
        assert NotificationOutbox.objects.get().status == DISPATCHED

    def test_a_lost_worker_cannot_overwrite_a_failure_either(self, user, no_kick):
        row = enqueue(user)
        stale = claim_rows()[0]
        NotificationOutbox.objects.filter(pk=row.pk).update(locked_at=ago(500))
        claim_rows()
        with failing_dispatch(Boom("late")):
            assert process_row(stale) == LOST
        assert NotificationOutbox.objects.get().status == PROCESSING


# --------------------------------------------------------------------------- #
# Retry, backoff, dead letters                                                #
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestRetryAndDeadLetter:
    def test_a_failed_hand_off_is_retried_later_with_backoff(self, user, no_kick):
        row = enqueue(user)
        before = timezone.now()
        with failing_dispatch(Boom("db hiccup")):
            summary = dispatch_due()
        row.refresh_from_db()
        assert summary[RETRY] == 1
        assert row.status == PENDING and row.attempts == 1
        assert row.error_class == "transient" and "Boom: db hiccup" in row.last_error
        assert row.locked_by == "" and row.locked_at is None
        assert (
            before + timedelta(seconds=29)
            <= row.next_attempt_at
            <= timezone.now() + timedelta(seconds=31)
        )
        # not due yet: a sweep leaves it alone
        assert dispatch_due()["claimed"] == 0

    def test_the_delay_doubles_with_each_failed_attempt(self, user, no_kick):
        row = enqueue(user)
        delays = []
        for _ in range(2):
            NotificationOutbox.objects.filter(pk=row.pk).update(next_attempt_at=ago(1))
            with failing_dispatch(Boom("x")):
                dispatch_due()
            row.refresh_from_db()
            delays.append(round((row.next_attempt_at - timezone.now()).total_seconds()))
        assert delays[0] in (29, 30) and delays[1] in (59, 60)

    def test_a_retry_that_succeeds_clears_the_error(self, user, prefs, no_kick):
        row = enqueue(user)
        with failing_dispatch(Boom("x")):
            dispatch_due()
        NotificationOutbox.objects.filter(pk=row.pk).update(next_attempt_at=ago(1))
        with patch(WEBHOOK_DELIVER, return_value=True):
            assert dispatch_due()[DISPATCHED] == 1
        row.refresh_from_db()
        assert row.status == DISPATCHED and row.attempts == 2
        assert row.last_error == "" and row.error_class == ""

    def test_the_last_attempt_dead_letters_the_row(self, user, no_kick):
        row = enqueue(user, source="progress.UserBadge:9")
        for _ in range(3):
            NotificationOutbox.objects.filter(pk=row.pk).update(next_attempt_at=ago(1))
            with failing_dispatch(Boom("still broken")):
                dispatch_due()
        row.refresh_from_db()
        assert row.status == DEAD and row.attempts == 3 and row.dead_at
        assert "still broken" in row.last_error
        letter = NotificationDeadLetter.objects.get()
        assert letter.channel == "outbox" and letter.recipient == user
        assert letter.retry_count == 3
        assert letter.payload["outbox_id"] == row.pk
        assert letter.payload["source"] == "progress.UserBadge:9"
        # dead rows are not picked up again
        NotificationOutbox.objects.filter(pk=row.pk).update(next_attempt_at=ago(1))
        assert dispatch_due()["claimed"] == 0

    def test_a_permanent_error_does_not_waste_attempts(self, user, no_kick):
        row = enqueue(user)
        with failing_dispatch(ValueError("bad payload")):
            summary = dispatch_due()
        row.refresh_from_db()
        assert summary[DEAD] == 1
        assert row.status == DEAD and row.attempts == 1
        assert row.error_class == "permanent"
        assert NotificationDeadLetter.objects.count() == 1

    def test_a_failed_attempt_leaves_no_half_written_notification(
        self, user, prefs, no_kick
    ):
        enqueue(user)
        real = tasks.dispatch_notification

        def write_then_fail(*args, **kwargs):
            real(*args, **kwargs)
            raise Boom("after writing the rows")

        with failing_dispatch(Boom("unused")) as patched:
            patched.side_effect = write_then_fail
            dispatch_due()
        assert Notification.objects.count() == 0
        assert NotificationDelivery.objects.count() == 0

    def test_a_row_that_keeps_killing_its_worker_ends_up_dead(self, user, no_kick):
        row = enqueue(user)
        for _ in range(3):  # three workers claimed it and died without a word
            claim_rows()
            NotificationOutbox.objects.filter(pk=row.pk).update(locked_at=ago(600))
        assert dispatch_due()[DEAD] == 1
        row.refresh_from_db()
        assert row.status == DEAD and row.attempts == 4
        assert "repeated worker failures" in row.last_error

    def test_one_bad_row_does_not_stop_the_others(self, user, prefs, no_kick):
        bad = enqueue(user, key="bad")
        good = enqueue(user, key="good")
        real = tasks.dispatch_notification

        def pick(recipient, *args, **kwargs):
            if kwargs["dedupe_key"] == "bad":
                raise Boom("this one fails")
            return real(recipient, *args, **kwargs)

        with (
            patch.object(tasks, "dispatch_notification", side_effect=pick),
            patch(WEBHOOK_DELIVER, return_value=True),
        ):
            summary = dispatch_due()
        assert summary[RETRY] == 1 and summary[DISPATCHED] == 1
        assert NotificationOutbox.objects.get(pk=bad.pk).status == PENDING
        assert NotificationOutbox.objects.get(pk=good.pk).status == DISPATCHED

    def test_requeueing_a_dead_row_gives_it_fresh_attempts(self, user, prefs, no_kick):
        row = enqueue(user)
        with failing_dispatch(ValueError("x")):
            dispatch_due()
        assert NotificationOutbox.objects.get().status == DEAD
        assert requeue_dead([row.pk + 999]) == 0
        assert requeue_dead([row.pk]) == 1
        with patch(WEBHOOK_DELIVER, return_value=True):
            assert dispatch_due()[DISPATCHED] == 1
        row.refresh_from_db()
        assert row.status == DISPATCHED and row.attempts == 1


# --------------------------------------------------------------------------- #
# Metrics and reconciliation                                                  #
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestMetricsAndReconciliation:
    def seed(self, user):
        pending_old = enqueue(user, key="pending-old")
        pending_new = enqueue(user, key="pending-new")
        waiting = enqueue(user, key="waiting-for-retry")
        stuck = enqueue(user, key="stuck")
        done = enqueue(user, key="done")
        dead = enqueue(user, key="dead")
        update = NotificationOutbox.objects.filter
        update(pk=pending_old.pk).update(created_at=ago(900))
        update(pk=pending_new.pk).update(created_at=ago(5))
        update(pk=waiting.pk).update(
            created_at=ago(60), next_attempt_at=timezone.now() + timedelta(hours=1)
        )
        update(pk=stuck.pk).update(
            status=PROCESSING, locked_at=ago(600), created_at=ago(700), attempts=1
        )
        update(pk=done.pk).update(status=DISPATCHED, dispatched_at=ago(10))
        update(pk=dead.pk).update(
            status=DEAD,
            dead_at=ago(3000),
            attempts=3,
            error_class="permanent",
            last_error="ValueError: nope",
        )
        return {"stuck": stuck, "dead": dead, "done": done}

    def test_stats_show_backlog_age_and_dead_rows(self, user, no_kick):
        self.seed(user)
        stats = outbox_stats()
        assert (stats["pending"], stats["processing"]) == (3, 1)
        assert (stats["dispatched"], stats["dead"]) == (1, 1)
        assert stats["backlog"] == 4
        assert stats["overdue"] == 3  # two due pending rows + the expired lease
        assert stats["stale_processing"] == 1
        assert 895 <= stats["oldest_backlog_age_seconds"] <= 905
        assert 2995 <= stats["oldest_dead_age_seconds"] <= 3005

    def test_stats_of_an_empty_outbox(self, db):
        stats = outbox_stats()
        assert stats["backlog"] == 0 and stats["dead"] == 0
        assert stats["oldest_backlog_age_seconds"] is None
        assert stats["oldest_dead_age_seconds"] is None

    def test_the_prometheus_collector_exposes_the_same_numbers(self, user, no_kick):
        self.seed(user)
        families = {f.name: f for f in metrics.OutboxCollector().collect()}
        samples = {
            s.labels.get("status", s.name): s.value
            for s in families[metrics.OUTBOX_ROWS].samples
        }
        assert samples == {"pending": 3, "processing": 1, "dispatched": 1, "dead": 1}
        backlog_age = families[metrics.OUTBOX_BACKLOG_AGE].samples[0].value
        assert 895 <= backlog_age <= 905
        assert families[metrics.OUTBOX_OVERDUE].samples[0].value == 3
        assert 2995 <= families[metrics.OUTBOX_DEAD_AGE].samples[0].value <= 3005

    def test_the_collector_is_registered_and_survives_a_database_error(self):
        from prometheus_client import REGISTRY

        metrics.register_outbox_collector()
        assert REGISTRY.get_sample_value(metrics.OUTBOX_OVERDUE) is not None
        with patch.object(outbox, "outbox_stats", side_effect=RuntimeError("db down")):
            assert list(metrics.OutboxCollector().collect()) == []

    def test_reconcile_lists_dead_rows(self, user, no_kick):
        refs = self.seed(user)
        report = reconcile()
        assert [r["id"] for r in report["dead_rows"]] == [refs["dead"].pk]
        assert report["dead_rows"][0]["last_error"] == "ValueError: nope"

    def test_reconcile_counts_dispatched_rows_whose_deliveries_failed(
        self, user, prefs, no_kick
    ):
        ok = enqueue(user, key="ok")
        broken = enqueue(user, key="broken")
        with patch(
            WEBHOOK_DELIVER,
            side_effect=lambda delivery, *a, **k: delivery.dedupe_key != "broken",
        ):
            dispatch_due()
        # a channel failing permanently is visible next to the outbox
        NotificationDelivery.objects.filter(
            dedupe_key=broken.idempotency_key, channel="webhook"
        ).update(status="failed")
        assert NotificationOutbox.objects.get(pk=ok.pk).status == DISPATCHED
        assert reconcile()["dispatched_with_failed_deliveries"] == 1
        assert reconcile(since_days=0)["dispatched_with_failed_deliveries"] == 0

    def test_purging_removes_only_old_dispatched_rows(self, user, no_kick, settings):
        old = enqueue(user, key="old")
        recent = enqueue(user, key="recent")
        pending = enqueue(user, key="pending")
        dead = enqueue(user, key="dead")
        update = NotificationOutbox.objects.filter
        update(pk=old.pk).update(status=DISPATCHED, dispatched_at=ago(200 * 86400))
        update(pk=recent.pk).update(status=DISPATCHED, dispatched_at=ago(86400))
        update(pk=pending.pk).update(created_at=ago(300 * 86400))
        update(pk=dead.pk).update(status=DEAD, dead_at=ago(300 * 86400))
        assert outbox.purge_dispatched() == 1
        assert set(NotificationOutbox.objects.values_list("pk", flat=True)) == {
            recent.pk,
            pending.pk,
            dead.pk,
        }
        settings.NOTIFICATION_DELIVERY_RETENTION_DAYS = 0
        update(pk=recent.pk).update(dispatched_at=ago(900 * 86400))
        assert outbox.purge_dispatched() == 0

    def test_the_purge_task_reports_the_outbox_too(self, user, no_kick):
        row = enqueue(user)
        NotificationOutbox.objects.filter(pk=row.pk).update(
            status=DISPATCHED, dispatched_at=ago(200 * 86400)
        )
        counts: Any = tasks.purge_notification_ledger_task()
        assert counts["outbox"] == 1 and "attempts" in counts


# --------------------------------------------------------------------------- #
# Management commands and wiring                                              #
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestCommands:
    def run(self, command, *args):
        out = StringIO()
        call_command(command, *args, stdout=out)
        return out.getvalue()

    def test_the_dispatch_command_runs_one_sweep(self, user, prefs, no_kick):
        enqueue(user, key="a")
        enqueue(user, key="b")
        with patch(WEBHOOK_DELIVER, return_value=True):
            output = self.run("dispatch_notification_outbox", "--batch-size", "1")
        assert "claimed=2" in output and "dispatched=2" in output
        assert NotificationOutbox.objects.filter(status=DISPATCHED).count() == 2

    def test_the_report_is_readable(self, user, no_kick):
        TestMetricsAndReconciliation().seed(user)
        output = self.run("reconcile_notification_outbox")
        assert "pending=3 processing=1 dispatched=1 dead=1" in output
        assert "stale_processing=1" in output
        assert "ValueError: nope" in output

    def test_the_report_can_be_json(self, user, no_kick):
        TestMetricsAndReconciliation().seed(user)
        data = json.loads(self.run("reconcile_notification_outbox", "--json"))
        assert data["dead"] == 1 and data["backlog"] == 4
        assert data["dead_rows"][0]["error_class"] == "permanent"

    def test_it_fails_on_dead_rows_when_asked(self, user, no_kick):
        TestMetricsAndReconciliation().seed(user)
        with pytest.raises(CommandError, match="1 dead outbox row"):
            self.run("reconcile_notification_outbox", "--fail-on-dead")

    def test_it_fails_when_the_backlog_is_too_old(self, user, no_kick):
        TestMetricsAndReconciliation().seed(user)
        with pytest.raises(CommandError, match="oldest undispatched row"):
            self.run("reconcile_notification_outbox", "--max-age", "300")
        assert "backlog=4" in self.run(
            "reconcile_notification_outbox", "--max-age", "5000"
        )

    def test_a_clean_outbox_passes_the_checks(self, db):
        self.run("reconcile_notification_outbox", "--fail-on-dead", "--max-age", "60")

    def test_dead_rows_can_be_requeued_from_the_command(self, user, no_kick):
        refs = TestMetricsAndReconciliation().seed(user)
        output = self.run(
            "reconcile_notification_outbox",
            "--requeue-dead",
            "--id",
            str(refs["dead"].pk),
        )
        assert "Requeued 1 dead outbox row(s)" in output
        assert NotificationOutbox.objects.get(pk=refs["dead"].pk).status == PENDING

    def test_the_sweep_is_scheduled(self):
        from django.conf import settings

        entry = settings.CELERY_BEAT_SCHEDULE["dispatch-notification-outbox"]
        assert entry["task"] == "apps.notifications.tasks.dispatch_notification_outbox"
