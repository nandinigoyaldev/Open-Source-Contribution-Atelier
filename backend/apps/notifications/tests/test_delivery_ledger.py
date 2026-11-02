"""Durable delivery ledger: attempts, dedupe, retry classification, recovery, retention (#3286)."""

import smtplib
from datetime import timedelta
from io import StringIO
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.notifications import tasks
from apps.notifications.delivery import (
    PERMANENT,
    TRANSIENT,
    DeliveryError,
    DeliveryResult,
    backoff_seconds,
    classify_failure,
    make_dedupe_key,
    normalize_result,
)
from apps.notifications.models import (
    Notification,
    NotificationAttempt,
    NotificationDeadLetter,
    NotificationDelivery,
    NotificationPreference,
)
from apps.notifications.retention import purge_notification_ledger
from apps.notifications.tasks import (
    dispatch_notification,
    process_notification_delivery,
    recover_stale_deliveries,
)

WEBHOOK_DELIVER = "apps.notifications.channels.webhook_channel.WebhookChannel.deliver"
PAYLOAD = {"notif_type": "badge", "title": "Hello", "message": "World", "meta": {}}


@pytest.fixture(autouse=True)
def ledger_settings(settings, db):
    from django.core.cache import cache

    cache.clear()
    settings.NOTIFICATION_MAX_ATTEMPTS = 3
    settings.NOTIFICATION_CLAIM_LEASE_SECONDS = 120
    settings.NOTIFICATION_STALE_AFTER_SECONDS = 300
    settings.NOTIFICATION_RATE_LIMIT_MAX_DEFERRALS = 2
    settings.CELERY_TASK_ALWAYS_EAGER = False


# Celery's decorators are not understood by the type checker (it reads ``self`` of a bound task as
# a parameter), so the tasks are called through ``Any``.
Preferences: Any = (
    NotificationPreference  # the type checker has no `.objects` for models
)
_deliver_task: Any = process_notification_delivery
_recover_task: Any = recover_stale_deliveries


def run_task(delivery_id, payload=None):
    return _deliver_task(delivery_id, payload)


def run_recovery():
    return _recover_task()


def make_delivery(user, channel="webhook", **kwargs):
    return NotificationDelivery.objects.create(
        recipient=user, channel=channel, status="pending", **kwargs
    )


def run(delivery, payload=PAYLOAD):
    result = run_task(delivery.id, payload)
    delivery.refresh_from_db()
    return result


class TestClassification:
    @pytest.mark.parametrize(
        "status,expected",
        [
            (400, PERMANENT),
            (401, PERMANENT),
            (403, PERMANENT),
            (404, PERMANENT),
            (410, PERMANENT),
            (408, TRANSIENT),
            (429, TRANSIENT),
            (500, TRANSIENT),
            (502, TRANSIENT),
            (503, TRANSIENT),
        ],
    )
    def test_http_status_decides(self, status, expected):
        assert classify_failure(DeliveryError("x", status_code=status)) == expected

    def test_an_explicit_flag_overrides_the_status(self):
        assert (
            classify_failure(DeliveryError("x", status_code=500, retryable=False))
            == PERMANENT
        )
        assert (
            classify_failure(DeliveryError("x", status_code=400, retryable=True))
            == TRANSIENT
        )

    def test_status_is_found_on_a_requests_style_response(self):
        exc = RuntimeError("bad gateway")
        setattr(exc, "response", MagicMock(status_code=502))
        assert classify_failure(exc) == TRANSIENT
        setattr(exc, "response", MagicMock(status_code=404))
        assert classify_failure(exc) == PERMANENT

    def test_status_is_found_on_a_provider_exception_attribute(self):
        class TwilioLike(Exception):
            status = 400

        assert classify_failure(TwilioLike("invalid number")) == PERMANENT

    def test_smtp_4xx_is_temporary_and_5xx_is_permanent(self):
        assert classify_failure(smtplib.SMTPResponseException(421, "busy")) == TRANSIENT
        assert (
            classify_failure(smtplib.SMTPResponseException(550, "no such user"))
            == PERMANENT
        )
        assert classify_failure(smtplib.SMTPRecipientsRefused({})) == PERMANENT
        assert classify_failure(smtplib.SMTPServerDisconnected("gone")) == TRANSIENT

    @pytest.mark.parametrize(
        "exc", [TimeoutError(), ConnectionError(), OSError(), RuntimeError("boom")]
    )
    def test_network_trouble_and_unknown_errors_are_worth_retrying(self, exc):
        assert classify_failure(exc) == TRANSIENT

    @pytest.mark.parametrize(
        "exc", [ValueError("bad"), TypeError("bad"), KeyError("k"), AttributeError("a")]
    )
    def test_bad_input_will_fail_the_same_way_again(self, exc):
        assert classify_failure(exc) == PERMANENT

    def test_results(self):
        assert normalize_result(True).success
        assert not normalize_result(False).success and normalize_result(False).retryable
        assert not normalize_result(None).success
        kept = DeliveryResult.sent(provider="x", message_id="1")
        assert normalize_result(kept) is kept
        assert DeliveryResult.permanent_failure("no").retryable is False
        assert DeliveryResult.transient_failure("later").retryable is True

    def test_backoff_doubles_and_is_capped(self):
        assert [backoff_seconds(n) for n in (1, 2, 3)] == [60, 120, 240]
        assert backoff_seconds(30) == 3600

    def test_dedupe_keys_are_stable_and_distinct(self):
        assert make_dedupe_key("badge", 1, 2) == make_dedupe_key("badge", 1, 2)
        assert make_dedupe_key("badge", 1, 2) != make_dedupe_key("badge", 1, 3)
        assert make_dedupe_key("a", "bc") != make_dedupe_key("ab", "c")
        assert len(make_dedupe_key("x" * 500)) <= 128


@pytest.mark.django_db
class TestAttemptLedger:
    def test_a_success_records_the_attempt_and_the_provider_answer(self, user):
        delivery = make_delivery(user)
        result = DeliveryResult.sent(
            provider="hook",
            message_id="m-1",
            status_code=202,
            response={"body": "queued"},
        )
        with patch(WEBHOOK_DELIVER, return_value=result):
            assert run(delivery) is True

        assert (
            delivery.status == "sent"
            and delivery.sent_at
            and delivery.claimed_at is None
        )
        assert (delivery.provider, delivery.provider_message_id) == ("hook", "m-1")
        assert delivery.provider_response == {"body": "queued"}
        attempt = delivery.attempts.get()
        assert attempt.outcome == "sent" and attempt.attempt_number == 1
        assert (attempt.provider, attempt.status_code, attempt.provider_message_id) == (
            "hook",
            202,
            "m-1",
        )
        assert attempt.finished_at and attempt.duration_ms is not None

    def test_a_plain_true_from_an_older_channel_still_works(self, user):
        delivery = make_delivery(user)
        with patch(WEBHOOK_DELIVER, return_value=True):
            assert run(delivery) is True
        assert delivery.status == "sent"
        assert delivery.attempts.get().outcome == "sent"

    def test_each_try_gets_its_own_numbered_row(self, user):
        delivery = make_delivery(user)
        with patch(WEBHOOK_DELIVER, side_effect=DeliveryError("down", status_code=503)):
            run(delivery)
            run(delivery)
        assert list(delivery.attempts.values_list("attempt_number", "outcome")) == [
            (1, "transient_failure"),
            (2, "transient_failure"),
        ]

    def test_long_provider_text_is_clipped(self, user):
        delivery = make_delivery(user)
        result = DeliveryResult.sent(provider="p", response={"body": "x" * 5000})
        with patch(WEBHOOK_DELIVER, return_value=result):
            run(delivery)
        assert len(delivery.provider_response["body"]) <= 1000

    def test_provider_metadata_that_is_not_plain_json_is_stored_as_text(self, user):
        delivery = make_delivery(user)
        result = DeliveryResult.sent(
            provider="p", response={"obj": object(), "n": 3, "ok": True, "none": None}
        )
        with patch(WEBHOOK_DELIVER, return_value=result):
            assert run(delivery) is True
        stored = delivery.provider_response
        assert stored["n"] == 3 and stored["ok"] is True and stored["none"] is None
        assert isinstance(stored["obj"], str)

    def test_the_payload_is_kept_so_a_retry_does_not_need_the_task_arguments(
        self, user
    ):
        delivery = make_delivery(user)
        deliver = MagicMock(side_effect=[DeliveryError("down", status_code=503), True])
        with patch(WEBHOOK_DELIVER, deliver):
            run(delivery)
            assert delivery.payload == PAYLOAD
            run_task(delivery.id, None)
        assert deliver.call_args_list[1].args[2] == PAYLOAD


@pytest.mark.django_db
class TestRetryClassification:
    def test_a_permanent_failure_is_not_retried(self, user):
        delivery = make_delivery(user)
        deliver = MagicMock(side_effect=DeliveryError("rejected", status_code=400))
        with patch(WEBHOOK_DELIVER, deliver):
            assert run(delivery) is False
        assert deliver.call_count == 1
        assert delivery.status == "failed" and delivery.error_class == "permanent"
        assert delivery.retry_count == 1 and delivery.next_retry_at is None
        dead = NotificationDeadLetter.objects.get(recipient=user, channel="webhook")
        assert "rejected" in dead.error_message and dead.payload == PAYLOAD

    def test_a_result_marked_permanent_is_not_retried_either(self, user):
        delivery = make_delivery(user)
        with patch(
            WEBHOOK_DELIVER, return_value=DeliveryResult.permanent_failure("no address")
        ):
            run(delivery)
        assert delivery.status == "failed" and delivery.error_class == "permanent"
        assert delivery.attempts.get().outcome == "permanent_failure"

    def test_a_transient_failure_waits_and_keeps_the_delivery_pending(self, user):
        delivery = make_delivery(user)
        with patch(WEBHOOK_DELIVER, side_effect=DeliveryError("busy", status_code=429)):
            run(delivery)
        assert delivery.status == "pending" and delivery.error_class == "transient"
        assert delivery.retry_count == 1 and delivery.claimed_at is None
        wait = (delivery.next_retry_at - timezone.now()).total_seconds()
        assert 50 < wait <= 60
        assert not NotificationDeadLetter.objects.exists()

    def test_the_wait_grows_and_the_last_try_dead_letters(self, user):
        delivery = make_delivery(user)
        waits = []
        with patch(WEBHOOK_DELIVER, side_effect=RuntimeError("Connection refused")):
            for _ in range(3):
                run(delivery)
                if delivery.next_retry_at:
                    waits.append(
                        round(
                            (delivery.next_retry_at - timezone.now()).total_seconds(),
                            -1,
                        )
                    )
        assert waits == [60.0, 120.0]
        assert delivery.status == "failed" and delivery.retry_count == 3
        assert NotificationDeadLetter.objects.filter(recipient=user).count() == 1

    def test_a_bare_false_counts_as_a_transient_failure(self, user):
        delivery = make_delivery(user)
        with patch(WEBHOOK_DELIVER, return_value=False):
            run(delivery)
        assert delivery.status == "pending" and delivery.error_class == "transient"

    def test_the_attempt_limit_is_configurable(self, user, settings):
        settings.NOTIFICATION_MAX_ATTEMPTS = 1
        delivery = make_delivery(user)
        with patch(WEBHOOK_DELIVER, side_effect=RuntimeError("down")):
            run(delivery)
        assert delivery.status == "failed"

    def test_an_unregistered_channel_is_a_permanent_failure(self, user):
        delivery = make_delivery(user, channel="carrier-pigeon")
        assert run(delivery) is False
        assert delivery.status == "failed" and delivery.error_class == "permanent"
        assert "not registered" in delivery.error_message

    def test_a_failure_on_the_network_is_retried_with_a_queued_task_when_a_worker_runs_it(
        self, user
    ):
        delivery = make_delivery(user)
        queued = []
        # run inside a real task request so it is not "called directly"
        with (
            patch(WEBHOOK_DELIVER, side_effect=ConnectionError("reset")),
            patch.object(
                tasks.process_notification_delivery,
                "apply_async",
                side_effect=lambda **kw: queued.append(kw),
            ),
            patch.object(tasks, "_can_schedule", return_value=True),
        ):
            run(delivery)
        assert queued and queued[0]["args"] == (delivery.id, None)
        assert 50 < queued[0]["countdown"] <= 60


@pytest.mark.django_db
class TestIdempotencyAndClaims:
    def test_a_sent_delivery_is_not_sent_again(self, user):
        delivery = make_delivery(user)
        deliver = MagicMock(return_value=True)
        with patch(WEBHOOK_DELIVER, deliver):
            assert run(delivery) is True
            assert run(delivery) is True  # the broker redelivered the task
        assert deliver.call_count == 1
        assert list(delivery.attempts.values_list("outcome", flat=True)) == [
            "sent",
            "skipped",
        ]

    def test_a_failed_delivery_stays_failed(self, user):
        delivery = make_delivery(user)
        with patch(WEBHOOK_DELIVER, side_effect=DeliveryError("no", status_code=400)):
            run(delivery)
        deliver = MagicMock(return_value=True)
        with patch(WEBHOOK_DELIVER, deliver):
            assert run(delivery) is False
        deliver.assert_not_called()

    def test_a_delivery_held_by_another_worker_is_left_alone(self, user):
        delivery = make_delivery(user, claimed_at=timezone.now())
        deliver = MagicMock(return_value=True)
        with patch(WEBHOOK_DELIVER, deliver):
            assert run(delivery) is False
        deliver.assert_not_called()
        assert not delivery.attempts.exists()

    def test_a_claim_older_than_the_lease_is_taken_over(self, user):
        delivery = make_delivery(
            user, claimed_at=timezone.now() - timedelta(minutes=10)
        )
        with patch(WEBHOOK_DELIVER, return_value=True):
            assert run(delivery) is True

    def test_a_missing_delivery_is_reported_not_raised(self, db):
        assert run_task(999999, PAYLOAD) is False

    def test_the_claim_is_released_after_each_outcome(self, user):
        for effect in (True, RuntimeError("x"), DeliveryError("n", status_code=400)):
            delivery = make_delivery(user)
            with patch(
                WEBHOOK_DELIVER,
                side_effect=[effect] if isinstance(effect, Exception) else None,
                return_value=effect,
            ):
                run(delivery)
            assert delivery.claimed_at is None


@pytest.mark.django_db
class TestRateLimiting:
    def test_being_rate_limited_defers_without_using_an_attempt(self, user):
        delivery = make_delivery(user)
        deliver = MagicMock(return_value=True)
        with (
            patch(WEBHOOK_DELIVER, deliver),
            patch.object(
                tasks.ChannelRateLimiter, "is_allowed", return_value=(False, 99)
            ),
        ):
            assert run(delivery) is False
        deliver.assert_not_called()
        assert delivery.status == "pending" and delivery.retry_count == 0
        assert (
            delivery.error_class == "rate_limited"
            and delivery.next_retry_at > timezone.now()
        )
        assert delivery.attempts.get().outcome == "rate_limited"
        assert not NotificationDeadLetter.objects.exists()

    def test_it_is_delivered_once_the_limit_clears(self, user):
        delivery = make_delivery(user)
        with (
            patch(WEBHOOK_DELIVER, return_value=True),
            patch.object(
                tasks.ChannelRateLimiter,
                "is_allowed",
                side_effect=[(False, 9), (True, 1)],
            ),
        ):
            run(delivery)
            assert run(delivery) is True
        assert delivery.status == "sent" and delivery.error_class == ""

    def test_it_gives_up_after_too_many_deferrals(self, user):
        delivery = make_delivery(user)
        with patch.object(
            tasks.ChannelRateLimiter, "is_allowed", return_value=(False, 9)
        ):
            for _ in range(3):  # limit is 2 deferrals
                run(delivery)
        assert delivery.status == "failed" and delivery.error_class == "rate_limited"
        assert NotificationDeadLetter.objects.filter(recipient=user).exists()


@pytest.mark.django_db
class TestDedupe:
    def prefs(self, user):
        pref, _ = Preferences.objects.get_or_create(user=user)
        pref.channel_preferences = {"badge": {"in_app": True, "webhook": True}}
        pref.save()

    def test_the_same_event_is_notified_once(self, user):
        self.prefs(user)
        with patch(WEBHOOK_DELIVER, return_value=True) as deliver:
            first = dispatch_notification(user, "badge", "T", "M", dedupe_key="badge:1")
            second = dispatch_notification(
                user, "badge", "T", "M", dedupe_key="badge:1"
            )
        assert {d.id for d in first} == {d.id for d in second}
        assert Notification.objects.filter(recipient=user).count() == 1
        assert NotificationDelivery.objects.filter(recipient=user).count() == len(first)
        assert deliver.call_count == 1

    def test_a_different_key_or_recipient_is_a_new_notification(
        self, user, django_user_model
    ):
        self.prefs(user)
        other = django_user_model.objects.create_user(
            username="other", email="o@example.com", password="x"
        )
        self.prefs(other)
        with patch(WEBHOOK_DELIVER, return_value=True):
            dispatch_notification(user, "badge", "T", "M", dedupe_key="k1")
            dispatch_notification(user, "badge", "T", "M", dedupe_key="k2")
            dispatch_notification(other, "badge", "T", "M", dedupe_key="k1")
        assert Notification.objects.filter(recipient=user).count() == 2
        assert Notification.objects.filter(recipient=other).count() == 1

    def test_without_a_key_nothing_changes(self, user):
        self.prefs(user)
        with patch(WEBHOOK_DELIVER, return_value=True):
            dispatch_notification(user, "badge", "T", "M")
            dispatch_notification(user, "badge", "T", "M")
        assert Notification.objects.filter(recipient=user).count() == 2

    def test_the_database_refuses_a_duplicate_key_but_allows_many_without_one(
        self, user
    ):
        make_delivery(user, dedupe_key="k")
        with (
            pytest.raises(IntegrityError),
            transaction.atomic(),  # pyright: ignore[reportGeneralTypeIssues]
        ):
            make_delivery(user, dedupe_key="k")
        make_delivery(user, dedupe_key="k", channel="email")  # another channel is fine
        make_delivery(user)
        make_delivery(user)

    def test_a_race_between_two_dispatches_leaves_one_notification(self, user):
        self.prefs(user)
        with patch(WEBHOOK_DELIVER, return_value=True):
            first = dispatch_notification(user, "badge", "T", "M", dedupe_key="race")

        real_filter = NotificationDelivery.objects.filter
        calls = {"n": 0}

        def blind_first_check(*args, **kwargs):
            calls["n"] += 1
            return (
                NotificationDelivery.objects.none()
                if calls["n"] == 1
                else real_filter(*args, **kwargs)
            )

        with patch.object(
            NotificationDelivery.objects, "filter", side_effect=blind_first_check
        ):
            second = dispatch_notification(user, "badge", "T", "M", dedupe_key="race")
        assert {d.id for d in second} == {d.id for d in first}
        assert Notification.objects.filter(recipient=user).count() == 1

    def test_a_failing_channel_does_not_hold_up_the_others(self, user):
        self.prefs(user)
        with patch(
            WEBHOOK_DELIVER, side_effect=DeliveryError("rejected", status_code=400)
        ):
            deliveries = dispatch_notification(user, "badge", "T", "M")
        by_channel = {d.channel: d.status for d in deliveries}
        assert by_channel["in_app"] == "sent"
        assert by_channel["webhook"] == "failed"


@pytest.mark.django_db
class TestRecovery:
    def queued(self) -> tuple[list, Any]:
        sent = []
        return sent, patch.object(
            tasks.process_notification_delivery,
            "apply_async",
            side_effect=lambda **kw: sent.append(kw["args"][0]),
        )

    def test_a_worker_that_died_mid_delivery_is_recovered_end_to_end(self, user):
        delivery = make_delivery(user)
        with (
            patch(WEBHOOK_DELIVER, side_effect=KeyboardInterrupt),
            pytest.raises(KeyboardInterrupt),
        ):
            run_task(delivery.id, PAYLOAD)
        delivery.refresh_from_db()
        assert delivery.claimed_at is not None
        assert delivery.attempts.get().outcome == "started"

        # time passes beyond the lease
        past = timezone.now() - timedelta(minutes=10)
        NotificationDelivery.objects.filter(pk=delivery.pk).update(
            claimed_at=past, created_at=past
        )
        NotificationAttempt.objects.filter(delivery=delivery).update(started_at=past)

        queued, queue = self.queued()
        with queue:
            summary = run_recovery()
        assert summary == {"abandoned": 1, "requeued": 1, "exhausted": 0}
        assert queued == [delivery.id]

        with patch(WEBHOOK_DELIVER, return_value=True):
            assert run_task(delivery.id, None) is True
        delivery.refresh_from_db()
        assert delivery.status == "sent" and delivery.retry_count == 1
        assert list(delivery.attempts.values_list("outcome", flat=True)) == [
            "abandoned",
            "sent",
        ]

    def test_a_retry_that_is_due_is_queued_and_one_that_is_not_yet_due_is_not(
        self, user
    ):
        due = make_delivery(
            user, next_retry_at=timezone.now() - timedelta(seconds=5), retry_count=1
        )
        later = make_delivery(
            user, next_retry_at=timezone.now() + timedelta(minutes=5), retry_count=1
        )
        queued, queue = self.queued()
        with queue:
            run_recovery()
        assert queued == [due.id]
        assert later.id not in queued

    def test_a_delivery_nobody_picked_up_is_queued_once_it_is_stale(self, user):
        fresh = make_delivery(user)
        stale = make_delivery(user)
        NotificationDelivery.objects.filter(pk=stale.pk).update(
            created_at=timezone.now() - timedelta(minutes=10)
        )
        queued, queue = self.queued()
        with queue:
            run_recovery()
        assert queued == [stale.id]
        assert fresh.id not in queued

    def test_deliveries_in_progress_or_finished_are_left_alone(self, user):
        old = timezone.now() - timedelta(hours=2)
        working = make_delivery(user, claimed_at=timezone.now())
        done = NotificationDelivery.objects.create(
            recipient=user, channel="webhook", status="sent"
        )
        NotificationDelivery.objects.filter(pk__in=[working.pk, done.pk]).update(
            created_at=old
        )
        queued, queue = self.queued()
        with queue:
            assert run_recovery() == {
                "abandoned": 0,
                "requeued": 0,
                "exhausted": 0,
            }
        assert queued == []

    def test_a_delivery_that_keeps_killing_its_worker_is_given_up_on(self, user):
        delivery = make_delivery(
            user, retry_count=3, error_message="worker died", payload=PAYLOAD
        )
        NotificationDelivery.objects.filter(pk=delivery.pk).update(
            next_retry_at=timezone.now() - timedelta(minutes=1)
        )
        queued, queue = self.queued()
        with queue:
            summary = run_recovery()
        assert summary["exhausted"] == 1 and queued == []
        delivery.refresh_from_db()
        assert delivery.status == "failed"
        assert NotificationDeadLetter.objects.filter(recipient=user).count() == 1

    def test_in_eager_mode_the_sweep_delivers_directly(self, user, settings):
        settings.CELERY_TASK_ALWAYS_EAGER = True
        delivery = make_delivery(
            user, payload=PAYLOAD, next_retry_at=timezone.now() - timedelta(seconds=1)
        )
        with patch(WEBHOOK_DELIVER, return_value=True):
            run_recovery()
        delivery.refresh_from_db()
        assert delivery.status == "sent"

    def test_a_failed_queue_call_leaves_the_delivery_for_the_next_sweep(self, user):
        delivery = make_delivery(
            user, next_retry_at=timezone.now() - timedelta(seconds=1)
        )
        with patch.object(
            tasks.process_notification_delivery,
            "apply_async",
            side_effect=OSError("broker down"),
        ):
            run_recovery()
        delivery.refresh_from_db()
        assert delivery.status == "pending" and delivery.claimed_at is None


@pytest.mark.django_db
class TestRetention:
    def ago(self, days):
        return timezone.now() - timedelta(days=days)

    def seed(self, user):
        rows = {}
        for name, status, days in [
            ("sent_old", "sent", 100),
            ("sent_recent", "sent", 10),
            ("failed_old", "failed", 200),
            ("failed_recent", "failed", 100),
            ("pending_ancient", "pending", 400),
        ]:
            d = NotificationDelivery.objects.create(
                recipient=user, channel="email", status=status
            )
            NotificationDelivery.objects.filter(pk=d.pk).update(
                created_at=self.ago(days), updated_at=self.ago(days)
            )
            rows[name] = d.pk
        old_attempt = NotificationAttempt.objects.create(
            delivery_id=rows["sent_recent"],
            attempt_number=1,
            outcome="sent",
            started_at=self.ago(40),
        )
        NotificationAttempt.objects.filter(pk=old_attempt.pk).update(
            created_at=self.ago(40)
        )
        NotificationAttempt.objects.create(
            delivery_id=rows["sent_recent"],
            attempt_number=2,
            outcome="sent",
            started_at=timezone.now(),
        )
        dead_old = NotificationDeadLetter.objects.create(
            recipient=user, channel="email"
        )
        NotificationDeadLetter.objects.filter(pk=dead_old.pk).update(
            failed_at=self.ago(300)
        )
        NotificationDeadLetter.objects.create(recipient=user, channel="email")
        return rows

    def test_old_rows_are_removed_and_recent_and_pending_ones_stay(self, user):
        rows = self.seed(user)
        counts = purge_notification_ledger()
        assert counts == {
            "attempts": 1,
            "deliveries": 1,
            "failed_deliveries": 1,
            "dead_letters": 1,
        }
        remaining = set(NotificationDelivery.objects.values_list("pk", flat=True))
        assert remaining == {
            rows["sent_recent"],
            rows["failed_recent"],
            rows["pending_ancient"],
        }
        assert NotificationAttempt.objects.count() == 1
        assert NotificationDeadLetter.objects.count() == 1

    def test_a_dry_run_changes_nothing(self, user):
        self.seed(user)
        before = (
            NotificationDelivery.objects.count(),
            NotificationAttempt.objects.count(),
        )
        counts = purge_notification_ledger(dry_run=True)
        assert counts["deliveries"] == 1 and counts["attempts"] == 1
        assert before == (
            NotificationDelivery.objects.count(),
            NotificationAttempt.objects.count(),
        )

    def test_a_window_of_zero_keeps_everything_of_that_kind(self, user, settings):
        settings.NOTIFICATION_DELIVERY_RETENTION_DAYS = 0
        settings.NOTIFICATION_FAILED_RETENTION_DAYS = 0
        rows = self.seed(user)
        counts = purge_notification_ledger()
        assert (
            counts["deliveries"] == 0
            and counts["failed_deliveries"] == 0
            and counts["dead_letters"] == 0
        )
        assert NotificationDelivery.objects.filter(pk=rows["sent_old"]).exists()

    def test_the_windows_are_configurable(self, user, settings):
        settings.NOTIFICATION_DELIVERY_RETENTION_DAYS = 5
        rows = self.seed(user)
        purge_notification_ledger()
        assert not NotificationDelivery.objects.filter(pk=rows["sent_recent"]).exists()

    def test_deleting_in_small_batches_removes_everything(self, user):
        for _ in range(7):
            d = NotificationDelivery.objects.create(
                recipient=user, channel="email", status="sent"
            )
            NotificationDelivery.objects.filter(pk=d.pk).update(
                created_at=self.ago(500)
            )
        assert purge_notification_ledger(batch_size=2)["deliveries"] == 7

    def test_removing_a_delivery_removes_its_attempts(self, user):
        d = NotificationDelivery.objects.create(
            recipient=user, channel="email", status="sent"
        )
        NotificationDelivery.objects.filter(pk=d.pk).update(created_at=self.ago(500))
        NotificationAttempt.objects.create(
            delivery=d, attempt_number=1, outcome="sent", started_at=timezone.now()
        )
        purge_notification_ledger()
        assert not NotificationAttempt.objects.filter(delivery_id=d.pk).exists()

    def test_the_management_command_reports(self, user):
        self.seed(user)
        out = StringIO()
        call_command("purge_notification_ledger", "--dry-run", stdout=out)
        text = out.getvalue()
        assert "Would remove 1 deliveries" in text and "attempts=30" in text
        call_command("purge_notification_ledger", stdout=out)
        assert "Removed 1 deliveries" in out.getvalue()

    def test_the_periodic_tasks_are_scheduled(self, settings):
        from django.conf import settings as real

        schedule = real.CELERY_BEAT_SCHEDULE
        assert (
            schedule["recover-stale-notification-deliveries"]["task"]
            == "apps.notifications.tasks.recover_stale_deliveries"
        )
        assert (
            schedule["purge-notification-ledger"]["task"]
            == "apps.notifications.tasks.purge_notification_ledger_task"
        )


@pytest.mark.django_db
class TestChannelsReportWhatTheyKnow:
    def test_webhook_success_carries_the_status_and_body(self, user):
        from apps.notifications.channels.webhook_channel import WebhookChannel

        pref, _ = Preferences.objects.get_or_create(user=user)
        pref.webhook_url = "https://hooks.example.com/x"
        pref.save()
        delivery = make_delivery(user)
        with patch(
            "requests.post", return_value=MagicMock(status_code=202, text="queued")
        ):
            result = WebhookChannel().deliver(delivery, user, PAYLOAD)
        assert isinstance(result, DeliveryResult)
        assert (
            result.success
            and result.status_code == 202
            and result.response == {"body": "queued"}
        )

    @pytest.mark.parametrize(
        "status,kind", [(500, TRANSIENT), (429, TRANSIENT), (404, PERMANENT)]
    )
    def test_webhook_errors_are_classified_by_status(self, user, status, kind):
        from apps.notifications.channels.webhook_channel import WebhookChannel

        pref, _ = Preferences.objects.get_or_create(user=user)
        pref.webhook_url = "https://hooks.example.com/x"
        pref.save()
        with patch(
            "requests.post", return_value=MagicMock(status_code=status, text="nope")
        ):
            with pytest.raises(DeliveryError) as info:
                WebhookChannel().deliver(make_delivery(user), user, PAYLOAD)
        assert info.value.status_code == status
        assert classify_failure(info.value) == kind

    def test_a_missing_address_is_permanent_for_email_sms_and_webhook(self, user):
        from apps.notifications.channels.email_channel import EmailChannel
        from apps.notifications.channels.sms_channel import SMSChannel
        from apps.notifications.channels.webhook_channel import WebhookChannel

        user.email = ""
        for channel in (EmailChannel(), SMSChannel(), WebhookChannel()):
            result = normalize_result(
                channel.deliver(
                    make_delivery(user, channel=channel.channel_id), user, PAYLOAD
                )
            )
            assert not result.success and result.retryable is False

    def test_a_missing_address_is_dead_lettered_after_one_try(self, user):
        user.email = ""
        user.save()
        delivery = make_delivery(user, channel="email")
        assert run(delivery) is False
        assert delivery.status == "failed" and delivery.retry_count == 1
        assert delivery.attempts.count() == 1

    def test_email_success_records_the_provider(self, user):
        delivery = make_delivery(user, channel="email")
        assert run(delivery) is True
        assert delivery.provider == "email"
