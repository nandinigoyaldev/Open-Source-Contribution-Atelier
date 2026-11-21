# pyright: reportAttributeAccessIssue=false, reportIndexIssue=false, reportOperatorIssue=false, reportArgumentType=false, reportReturnType=false, reportGeneralTypeIssues=false
from datetime import timedelta
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditEvent
from apps.monitoring import job_ops
from apps.monitoring.celery_monitor import (
    get_celery_stats,
    get_task_type_stats,
    on_task_failure,
    on_task_postrun,
    on_task_prerun,
    on_task_publish,
)
from apps.monitoring.models import TaskRun
from apps.monitoring.tasks import reap_stuck_task_runs

User = get_user_model()


def make_run(task_id="run-1", status="STARTED", **fields):
    fields.setdefault("task_name", "apps.demo.tasks.sync")
    return TaskRun.objects.create(task_id=task_id, status=status, **fields)


def events(operation):
    return AuditEvent.objects.filter(extra__operation=operation)


@pytest.fixture(autouse=True)
def _fresh_rate_limits(settings):
    """
    The rate limit middleware counts per IP in the cache, and these tests post a lot from
    one address. Start and leave every test with a clean counter so neither these tests
    nor the ones after them are throttled.
    """
    assert "locmem" in settings.CACHES["default"]["BACKEND"].lower()
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def admin_client(db):
    admin = User.objects.create_superuser(
        username="ops", password="pw12345!", email="ops@example.com"
    )
    client = APIClient()
    client.force_authenticate(user=admin)
    client.admin = admin
    return client


@pytest.fixture
def user_client(db):
    user = User.objects.create_user(
        username="learner", password="pw12345!", email="learner@example.com"
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def broker():
    """Replace Celery's control plane and publisher, so no broker is ever contacted."""
    with patch("apps.monitoring.job_ops.current_app") as app:
        app.send_task.return_value = MagicMock(id="new-task-id")
        yield app


def action_url(name, run):
    return reverse(f"celery-task-runs-{name}", kwargs={"pk": run.pk})


@pytest.mark.django_db
class TestOperatorAccess:
    @pytest.mark.parametrize(
        "url_name", ["celery-task-runs-list", "celery-task-stats", "celery-stats"]
    )
    def test_read_endpoints_are_admin_only(self, url_name, user_client, admin_client):
        url = reverse(url_name)
        assert APIClient().get(url).status_code in (401, 403)
        assert user_client.get(url).status_code == 403
        assert admin_client.get(url).status_code == 200

    def test_trigger_task_is_admin_only(self, user_client, admin_client):
        url = reverse("celery-trigger-task")
        assert user_client.post(url, {}).status_code == 403
        assert TaskRun.objects.count() == 0
        assert admin_client.post(url, {}).status_code == 202

    def test_cancel_and_retry_are_admin_only(self, user_client, broker):
        run = make_run(status="STUCK")
        assert user_client.post(action_url("cancel", run)).status_code == 403
        assert user_client.post(action_url("retry", run)).status_code == 403
        broker.control.revoke.assert_not_called()
        broker.send_task.assert_not_called()


@pytest.mark.django_db
class TestPayloadRedaction:
    def test_publish_stores_only_redacted_args(self):
        on_task_publish(
            sender="apps.demo.tasks.sync",
            headers={"id": "pub-1", "task": "apps.demo.tasks.sync"},
            body=(["visible"], {"password": "hunter2hunter2", "note": "ok"}, {}),
        )
        run = TaskRun.objects.get(task_id="pub-1")
        assert "hunter2hunter2" not in run.args_summary
        assert "[REDACTED]" in run.args_summary
        assert "visible" in run.args_summary

    def test_api_redacts_secrets_in_rows_it_did_not_write(self, admin_client):
        make_run(
            status="FAILURE",
            args_summary="kwargs={'url': 'https://x.test/?token=abc123secret'}",
            error_message="auth failed: Bearer abcdefghijklmnop123456",
        )
        row = admin_client.get(reverse("celery-task-runs-list")).data
        row = (row["results"] if isinstance(row, dict) else row)[0]
        assert "abc123secret" not in row["args_summary"]
        assert "abcdefghijklmnop123456" not in row["error_message"]

    def test_failure_reason_in_task_stats_is_redacted(self):
        make_run(
            status="FAILURE",
            error_message="login failed password=hunter2hunter2",
            finished_at=timezone.now(),
        )
        reason = get_task_type_stats()["per_task_stats"][0]["last_failure_reason"]
        assert "hunter2hunter2" not in reason


@pytest.mark.django_db
class TestPublishSignal:
    def test_records_pending_run_with_queue_time(self):
        on_task_publish(
            sender="apps.demo.tasks.sync",
            headers={"id": "pub-2", "task": "apps.demo.tasks.sync"},
            body=([], {}, {}),
        )
        run = TaskRun.objects.get(task_id="pub-2")
        assert run.status == "PENDING"
        assert run.task_name == "apps.demo.tasks.sync"
        assert run.queued_at is not None

    def test_republish_of_an_existing_run_changes_nothing(self):
        run = make_run("pub-3", status="RETRY")
        on_task_publish(
            sender="x", headers={"id": "pub-3", "task": "x"}, body=([], {}, {})
        )
        run.refresh_from_db()
        assert run.status == "RETRY"
        assert run.queued_at is None

    def test_a_failing_insert_does_not_raise_into_the_publisher(self):
        with patch.object(TaskRun.objects, "get_or_create", side_effect=OSError("db")):
            on_task_publish(
                sender="x", headers={"id": "pub-4", "task": "x"}, body=([], {}, {})
            )


@pytest.mark.django_db
class TestLeases:
    def test_prerun_takes_a_lease_and_postrun_releases_it(self, settings):
        settings.TASK_RUN_LEASE_SECONDS = 120
        sender = type("Task", (), {"name": "apps.demo.tasks.sync"})
        before = timezone.now()
        on_task_prerun(sender=sender, task_id="lease-1")
        run = TaskRun.objects.get(task_id="lease-1")
        assert run.heartbeat_at >= before
        assert run.lease_expires_at == run.heartbeat_at + timedelta(seconds=120)

        on_task_postrun(sender=sender, task_id="lease-1", state="SUCCESS")
        run.refresh_from_db()
        assert run.lease_expires_at is None

    def test_failure_releases_the_lease(self):
        sender = type("Task", (), {"name": "apps.demo.tasks.sync"})
        on_task_prerun(sender=sender, task_id="lease-2")
        on_task_failure(sender=sender, task_id="lease-2", exception=ValueError("x"))
        assert TaskRun.objects.get(task_id="lease-2").lease_expires_at is None

    def test_task_time_limit_sets_the_lease(self, settings):
        settings.TASK_RUN_LEASE_SECONDS = 120
        task = type("Task", (), {"name": "apps.demo.tasks.sync", "time_limit": 600})
        on_task_prerun(sender=task, task_id="lease-3", task=task)
        run = TaskRun.objects.get(task_id="lease-3")
        expected = timedelta(seconds=600 + job_ops.LEASE_GRACE_SECONDS)
        assert run.lease_expires_at - run.heartbeat_at == expected

    def test_heartbeat_extends_the_lease_and_revives_a_stuck_run(self):
        past = timezone.now() - timedelta(minutes=5)
        run = make_run("hb-1", status="STUCK", lease_expires_at=past)
        assert job_ops.touch_heartbeat("hb-1", lease_seconds=60) is True
        run.refresh_from_db()
        assert run.status == "STARTED"
        assert run.lease_expires_at > timezone.now()

    def test_heartbeat_ignores_finished_and_unknown_runs(self):
        make_run("hb-2", status="CANCELLED")
        assert job_ops.touch_heartbeat("hb-2") is False
        assert job_ops.touch_heartbeat("nope") is False
        assert TaskRun.objects.get(task_id="hb-2").status == "CANCELLED"


@pytest.mark.django_db
class TestReaper:
    def setup_method(self):
        now = timezone.now()
        self.expired = make_run("expired", lease_expires_at=now - timedelta(seconds=1))
        self.live = make_run("live", lease_expires_at=now + timedelta(minutes=5))
        self.unleased = make_run("unleased")
        self.done = make_run(
            "done", status="SUCCESS", lease_expires_at=now - timedelta(hours=1)
        )

    def test_marks_only_expired_running_runs_as_stuck(self):
        assert job_ops.reap_expired_runs() == 1
        statuses = dict(TaskRun.objects.values_list("task_id", "status"))
        assert statuses == {
            "expired": "STUCK",
            "live": "STARTED",
            "unleased": "STARTED",
            "done": "SUCCESS",
        }
        self.expired.refresh_from_db()
        assert "Lease expired" in self.expired.error_message

    def test_is_idempotent_and_audits_once(self):
        assert job_ops.reap_expired_runs() == 1
        assert job_ops.reap_expired_runs() == 0
        audit = events(job_ops.OP_MARKED_STUCK)
        assert audit.count() == 1
        event = audit.get()
        assert event.resource_id == str(self.expired.pk)
        assert event.extra["payload"]["from_status"] == "STARTED"
        assert event.extra["payload"]["to_status"] == "STUCK"

    def test_a_run_that_finishes_late_replaces_the_stuck_status(self):
        job_ops.reap_expired_runs()
        sender = type("Task", (), {"name": "apps.demo.tasks.sync"})
        on_task_postrun(sender=sender, task_id="expired", state="SUCCESS")
        self.expired.refresh_from_db()
        assert self.expired.status == "SUCCESS"

    def test_celery_task_and_command_run_the_reaper(self):
        assert reap_stuck_task_runs() == {"marked_stuck": 1}
        self.live.lease_expires_at = timezone.now() - timedelta(seconds=1)
        self.live.save()
        out = StringIO()
        call_command("reap_stuck_task_runs", stdout=out)
        assert "Marked 1 task run(s) as stuck" in out.getvalue()


@pytest.mark.django_db
class TestCancel:
    def test_cancels_a_queued_run_and_audits_it(self, admin_client, broker):
        run = make_run(status="PENDING", queued_at=timezone.now())
        res = admin_client.post(action_url("cancel", run))
        assert res.status_code == 200
        assert res.data["status"] == "cancelled"
        run.refresh_from_db()
        assert run.status == "CANCELLED"
        assert run.finished_at is not None
        broker.control.revoke.assert_called_once_with(run.task_id, terminate=False)
        event = events(job_ops.OP_CANCELLED).get()
        assert event.actor == admin_client.admin
        assert event.resource_id == str(run.pk)
        assert event.extra["payload"]["from_status"] == "PENDING"

    def test_is_idempotent(self, admin_client, broker):
        run = make_run(status="PENDING")
        url = action_url("cancel", run)
        assert admin_client.post(url).data["status"] == "cancelled"
        again = admin_client.post(url)
        assert again.status_code == 200
        assert again.data["status"] == "already_cancelled"
        assert broker.control.revoke.call_count == 1
        assert events(job_ops.OP_CANCELLED).count() == 1

    def test_stuck_run_is_terminated(self, admin_client, broker):
        run = make_run(status="STUCK")
        assert admin_client.post(action_url("cancel", run)).status_code == 200
        broker.control.revoke.assert_called_once_with(run.task_id, terminate=True)

    @pytest.mark.parametrize("status", ["STARTED", "SUCCESS", "FAILURE"])
    def test_refuses_a_run_that_is_running_or_finished(
        self, status, admin_client, broker
    ):
        run = make_run(status=status)
        res = admin_client.post(action_url("cancel", run))
        assert res.status_code == 409
        assert res.data["status"] == "not_cancellable"
        run.refresh_from_db()
        assert run.status == status
        broker.control.revoke.assert_not_called()
        assert events(job_ops.OP_CANCELLED).count() == 0

    def test_broker_outage_leaves_the_run_untouched(self, admin_client, broker):
        broker.control.revoke.side_effect = ConnectionError("broker down")
        finished = timezone.now() - timedelta(minutes=1)
        run = make_run(status="RETRY", finished_at=finished)
        res = admin_client.post(action_url("cancel", run))
        assert res.status_code == 503
        run.refresh_from_db()
        assert run.status == "RETRY"
        assert run.finished_at == finished
        assert events(job_ops.OP_CANCELLED).count() == 0


@pytest.mark.django_db
class TestRetry:
    @pytest.mark.parametrize("status", ["FAILURE", "STUCK", "CANCELLED"])
    def test_retries_and_audits(self, status, admin_client, broker):
        run = make_run(status=status)
        res = admin_client.post(action_url("retry", run))
        assert res.status_code == 202
        assert res.data["status"] == "queued"
        assert res.data["new_task_id"] == "new-task-id"
        run.refresh_from_db()
        assert run.status == "RETRY"
        assert run.retry_count == 1
        broker.send_task.assert_called_once_with(run.task_name)
        event = events(job_ops.OP_RETRIED).get()
        assert event.actor == admin_client.admin
        assert event.extra["payload"]["from_status"] == status
        assert event.extra["payload"]["new_task_id"] == "new-task-id"

    def test_second_retry_does_not_dispatch_again(self, admin_client, broker):
        run = make_run(status="STUCK")
        url = action_url("retry", run)
        assert admin_client.post(url).status_code == 202
        again = admin_client.post(url)
        assert again.status_code == 200
        assert again.data["status"] == "already_queued"
        run.refresh_from_db()
        assert run.retry_count == 1
        assert broker.send_task.call_count == 1
        assert events(job_ops.OP_RETRIED).count() == 1

    def test_refuses_a_successful_run(self, admin_client, broker):
        run = make_run(status="SUCCESS")
        res = admin_client.post(action_url("retry", run))
        assert res.status_code == 409
        assert res.data["status"] == "not_retryable"
        broker.send_task.assert_not_called()

    def test_broker_outage_is_reported_and_changes_nothing(self, admin_client, broker):
        broker.send_task.side_effect = ConnectionError("broker down")
        run = make_run(status="FAILURE")
        res = admin_client.post(action_url("retry", run))
        assert res.status_code == 503
        run.refresh_from_db()
        assert (run.status, run.retry_count) == ("FAILURE", 0)
        assert events(job_ops.OP_RETRIED).count() == 0


@pytest.mark.django_db
class TestStats:
    def stats_with_workers(self, alive):
        inspect = MagicMock()
        inspect.ping.return_value = {name: {"ok": "pong"} for name in alive}
        inspect.active.return_value = {name: [] for name in alive}
        inspect.reserved.return_value = {name: [] for name in alive}
        with patch("celery.current_app") as app:
            app.control.inspect.return_value = inspect
            return get_celery_stats()

    def test_queue_age_is_the_oldest_pending_publish(self):
        now = timezone.now()
        make_run("q-old", status="PENDING", queued_at=now - timedelta(seconds=300))
        make_run("q-new", status="PENDING", queued_at=now - timedelta(seconds=10))
        make_run("q-running", status="STARTED", queued_at=now - timedelta(hours=2))
        stats = self.stats_with_workers(["w1"])
        assert stats["pending_runs"] == 2
        assert 299 <= stats["oldest_queued_age_seconds"] <= 310

    def test_no_pending_runs_has_no_age(self):
        stats = self.stats_with_workers(["w1"])
        assert stats["pending_runs"] == 0
        assert stats["oldest_queued_age_seconds"] is None

    def test_worker_heartbeat_is_healthy_when_workers_answer(self):
        beat = timezone.now() - timedelta(seconds=5)
        make_run("hb-run", heartbeat_at=beat)
        heartbeat = self.stats_with_workers(["w2", "w1"])["worker_heartbeat"]
        assert heartbeat["status"] == "healthy"
        assert heartbeat["workers_alive"] == ["w1", "w2"]
        assert heartbeat["last_task_heartbeat_at"] == beat.isoformat()

    def test_worker_heartbeat_is_down_when_nobody_answers(self):
        stats = self.stats_with_workers([])
        assert stats["worker_heartbeat"]["status"] == "down"
        assert stats["worker_count"] == 0

    def test_worker_heartbeat_is_degraded_when_a_run_is_stuck(self):
        make_run("stuck-run", status="STUCK")
        stats = self.stats_with_workers(["w1"])
        assert stats["worker_heartbeat"]["status"] == "degraded"
        assert stats["stuck_runs"] == 1

    def test_stuck_runs_can_be_filtered(self, admin_client):
        make_run("s-1", status="STUCK")
        make_run("s-2", status="STARTED")
        data = admin_client.get(reverse("celery-task-runs-list") + "?status=STUCK").data
        results = data["results"] if isinstance(data, dict) else data
        assert [r["task_id"] for r in results] == ["s-1"]

    def test_pending_rows_report_their_queue_age(self, admin_client):
        make_run(
            "age-1", status="PENDING", queued_at=timezone.now() - timedelta(seconds=90)
        )
        data = admin_client.get(reverse("celery-task-runs-list")).data
        row = (data["results"] if isinstance(data, dict) else data)[0]
        assert 89 <= row["queue_age_seconds"] <= 100
