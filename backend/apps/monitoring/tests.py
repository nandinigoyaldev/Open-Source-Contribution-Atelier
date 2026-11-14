import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.monitoring.celery_monitor import (
    get_celery_stats,
    get_task_type_stats,
    on_task_failure,
    on_task_postrun,
    on_task_prerun,
    on_task_retry,
)
from apps.monitoring.models import TaskRun

User = get_user_model()


@pytest.mark.django_db
class TestCeleryMonitoring:
    def setup_method(self):
        TaskRun.objects.all().delete()
        self.client = APIClient()
        self.normal_user = User.objects.create_user(
            username="normaluser", password="password123", email="user@example.com"
        )
        self.admin_user = User.objects.create_superuser(
            username="adminuser", password="password123", email="admin@example.com"
        )

    def test_task_run_signals(self):
        # 1. Test prerun signal
        task_id = "test-task-123"
        task_name = "apps.notifications.tasks.send_email"
        on_task_prerun(
            sender=type("Task", (), {"name": task_name}),
            task_id=task_id,
            args=("arg1",),
            kwargs={"k": "v"},
        )

        run = TaskRun.objects.get(task_id=task_id)
        assert run.task_name == task_name
        assert run.status == "STARTED"

        # 2. Test postrun signal
        on_task_postrun(
            sender=type("Task", (), {"name": task_name}),
            task_id=task_id,
            state="SUCCESS",
        )
        run.refresh_from_db()
        assert run.status == "SUCCESS"
        assert run.finished_at is not None
        assert run.duration is not None

        # 3. Test failure signal
        fail_task_id = "test-fail-456"
        on_task_prerun(
            sender=type("Task", (), {"name": task_name}), task_id=fail_task_id
        )
        on_task_failure(
            sender=type("Task", (), {"name": task_name}),
            task_id=fail_task_id,
            exception=ValueError("Connection reset"),
        )
        fail_run = TaskRun.objects.get(task_id=fail_task_id)
        assert fail_run.status == "FAILURE"
        assert "Connection reset" in fail_run.error_message

        # 4. Test retry signal
        on_task_retry(
            sender=type("Task", (), {"name": task_name}),
            request=type("Request", (), {"id": fail_task_id}),
            reason="Temporary timeout",
        )
        fail_run.refresh_from_db()
        assert fail_run.status == "RETRY"
        assert fail_run.retry_count == 1

    def test_celery_stats_helper(self):
        stats = get_celery_stats()
        assert "worker_count" in stats
        assert "active_tasks" in stats
        assert "reserved_tasks" in stats
        assert "total_queue_depth" in stats

    def test_get_task_type_stats(self):
        TaskRun.objects.create(
            task_id="t1", task_name="task_a", status="SUCCESS", duration=1.5
        )
        TaskRun.objects.create(
            task_id="t2",
            task_name="task_a",
            status="FAILURE",
            duration=0.5,
            error_message="DB connection error",
        )
        stats = get_task_type_stats()
        assert "per_task_stats" in stats
        assert "top_failing_tasks" in stats
        assert "sparkline_24h" in stats
        assert len(stats["top_failing_tasks"]) == 1
        assert stats["top_failing_tasks"][0]["task_name"] == "task_a"

    def test_admin_permissions(self):
        url = reverse("celery-stats")

        # Unauthenticated request -> 401
        res = self.client.get(url)
        assert res.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]

        # Normal user -> 403
        self.client.force_authenticate(user=self.normal_user)
        res = self.client.get(url)
        assert res.status_code == status.HTTP_403_FORBIDDEN

        # Staff/Admin user -> 200
        self.client.force_authenticate(user=self.admin_user)
        res = self.client.get(url)
        assert res.status_code == status.HTTP_200_OK
        assert "worker_count" in res.data

    def test_task_runs_filtering_and_search(self):
        self.client.force_authenticate(user=self.admin_user)
        TaskRun.objects.create(
            task_id="task-111", task_name="send_digest", status="SUCCESS"
        )
        TaskRun.objects.create(
            task_id="task-222",
            task_name="sync_repo",
            status="FAILURE",
            error_message="Git auth failed",
        )

        url = reverse("celery-task-runs-list")

        # Search for "digest"
        res = self.client.get(f"{url}?search=digest")
        assert res.status_code == status.HTTP_200_OK
        results = res.data.get("results") if isinstance(res.data, dict) else res.data
        assert len(results) == 1
        assert results[0]["task_name"] == "send_digest"

        # Filter by status "FAILURE"
        res = self.client.get(f"{url}?status=FAILURE")
        assert res.status_code == status.HTTP_200_OK
        results = res.data.get("results") if isinstance(res.data, dict) else res.data
        assert len(results) == 1
        assert results[0]["task_name"] == "sync_repo"

    def test_task_arguments_redaction(self):
        task_id = "test-redact-123"
        on_task_prerun(
            sender=type("Task", (), {"name": "sensitive_task"}),
            task_id=task_id,
            args=("public_arg",),
            kwargs={
                "password": "supersecretpassword",
                "api_key": "live_key_999",
                "safe_field": "visible_data",
                "nested": {"token": "secret_token"},
            },
        )
        run = TaskRun.objects.get(task_id=task_id)
        assert "supersecretpassword" not in run.args_summary
        assert "live_key_999" not in run.args_summary
        assert "secret_token" not in run.args_summary
        assert "[REDACTED]" in run.args_summary
        assert "visible_data" in run.args_summary

    def test_correlation_id_and_age_filtering(self):
        from datetime import timedelta
        from django.utils import timezone

        self.client.force_authenticate(user=self.admin_user)
        now = timezone.now()
        TaskRun.objects.create(
            task_id="t-corr-1",
            task_name="task_a",
            correlation_id="corr-abc-123",
            status="SUCCESS",
            started_at=now,
        )
        TaskRun.objects.create(
            task_id="t-corr-2",
            task_name="task_b",
            correlation_id="corr-xyz-789",
            status="FAILURE",
            started_at=now - timedelta(hours=5),
        )

        url = reverse("celery-task-runs-list")

        # Filter by correlation_id
        res = self.client.get(f"{url}?correlation_id=corr-abc-123")
        assert res.status_code == status.HTTP_200_OK
        results = res.data.get("results") if isinstance(res.data, dict) else res.data
        assert len(results) == 1
        assert results[0]["task_id"] == "t-corr-1"

        # Filter by age_hours (only within last 2 hours)
        res = self.client.get(f"{url}?age_hours=2")
        assert res.status_code == status.HTTP_200_OK
        results = res.data.get("results") if isinstance(res.data, dict) else res.data
        assert len(results) == 1
        assert results[0]["task_id"] == "t-corr-1"

    def test_retry_action_authorization_and_idempotency(self):
        from datetime import timedelta
        from django.utils import timezone

        run = TaskRun.objects.create(
            task_id="fail-task-to-retry",
            task_name="test_retry_task",
            status="FAILURE",
            started_at=timezone.now() - timedelta(minutes=5),
            retry_count=0,
        )

        url = reverse("celery-task-runs-retry", kwargs={"pk": run.id})

        # Non-admin -> 403 Forbidden
        self.client.force_authenticate(user=self.normal_user)
        res = self.client.post(url)
        assert res.status_code == status.HTTP_403_FORBIDDEN

        # Admin -> 202 Accepted
        self.client.force_authenticate(user=self.admin_user)
        res = self.client.post(url)
        assert res.status_code == status.HTTP_202_ACCEPTED
        run.refresh_from_db()
        assert run.status == "RETRY"
        assert run.retry_count == 1

        # Idempotent retry within 60s
        run.status = "STARTED"
        run.started_at = timezone.now()
        run.save()
        res_idempotent = self.client.post(url)
        assert res_idempotent.status_code == status.HTTP_200_OK
        assert res_idempotent.data["status"] == "already_queued"

    def test_retention_cleanup_command(self):
        from datetime import timedelta
        from django.core.management import call_command
        from django.utils import timezone

        old_run = TaskRun.objects.create(
            task_id="old-task",
            task_name="old_job",
            status="SUCCESS",
            started_at=timezone.now() - timedelta(days=40),
        )
        recent_run = TaskRun.objects.create(
            task_id="recent-task",
            task_name="recent_job",
            status="SUCCESS",
            started_at=timezone.now() - timedelta(days=5),
        )

        call_command("cleanup_old_task_runs", days=30)
        assert not TaskRun.objects.filter(id=old_run.id).exists()
        assert TaskRun.objects.filter(id=recent_run.id).exists()
