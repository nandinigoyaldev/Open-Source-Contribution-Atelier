import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from django.utils import timezone
from rest_framework.test import APIClient

from apps.monitoring.collectors import (
    PRIORITY_QUEUES,
    CeleryMetricsCollector,
    calculate_percentiles,
    get_active_workers_info,
    get_redis_queue_lengths,
    get_task_duration_percentiles,
    get_unacknowledged_task_count,
    register_collectors,
)
from apps.monitoring.models import TaskRun


def test_calculate_percentiles_empty_and_normal():
    # Empty list
    empty_res = calculate_percentiles([])
    assert empty_res == {"0.5": 0.0, "0.95": 0.0, "0.99": 0.0}

    # 100 samples from 1.0 to 100.0
    samples = [float(i) for i in range(1, 101)]
    res = calculate_percentiles(samples)
    assert 49.0 <= res["0.5"] <= 51.0
    assert 94.0 <= res["0.95"] <= 96.0
    assert 98.0 <= res["0.99"] <= 100.0


def test_get_redis_queue_lengths():
    with patch("redis.Redis.from_url") as mock_from_url:
        mock_r = MagicMock()
        mock_r.llen.side_effect = lambda q: 42 if q == "high_priority" else 10
        mock_from_url.return_value = mock_r

        lengths = get_redis_queue_lengths()
        for q in PRIORITY_QUEUES:
            assert q in lengths
        assert lengths["high_priority"] == 42
        assert lengths["default"] == 10


@pytest.mark.django_db
def test_get_unacknowledged_task_count():
    TaskRun.objects.all().delete()
    TaskRun.objects.create(
        task_id="unacked-1",
        task_name="task.unacked",
        status="STARTED",
    )
    TaskRun.objects.create(
        task_id="unacked-2",
        task_name="task.unacked",
        status="STARTED",
    )
    TaskRun.objects.create(
        task_id="done-1",
        task_name="task.done",
        status="SUCCESS",
    )

    count = get_unacknowledged_task_count()
    assert count >= 2


@pytest.mark.django_db
def test_get_task_duration_percentiles():
    TaskRun.objects.all().delete()
    # Create 20 successful tasks with distinct durations
    for i in range(1, 21):
        TaskRun.objects.create(
            task_id=f"run-{i}",
            task_name="apps.tasks.send_mail",
            status="SUCCESS",
            duration=float(i),
            finished_at=timezone.now(),
        )

    overall, per_task = get_task_duration_percentiles()
    assert "0.5" in overall
    assert "0.95" in overall
    assert "0.99" in overall
    assert overall["0.5"] > 0
    assert "apps.tasks.send_mail" in per_task
    assert per_task["apps.tasks.send_mail"]["0.95"] >= overall["0.5"]


@pytest.mark.django_db
def test_celery_metrics_collector_collect():
    collector = CeleryMetricsCollector()
    metrics = list(collector.collect())

    metric_names = [m.name for m in metrics]
    assert "celery_queue_length" in metric_names
    assert "celery_unacknowledged_tasks" in metric_names
    assert "celery_task_execution_duration_seconds" in metric_names
    assert "celery_active_workers" in metric_names
    assert "celery_worker_heartbeat_status" in metric_names

    # Check queue labels
    queue_metric = next(m for m in metrics if m.name == "celery_queue_length")
    queue_labels = [sample.labels["queue"] for sample in queue_metric.samples]
    for q in PRIORITY_QUEUES:
        assert q in queue_labels

    # Check duration percentiles labels
    dur_metric = next(
        m for m in metrics if m.name == "celery_task_execution_duration_seconds"
    )
    quantiles = [sample.labels["quantile"] for sample in dur_metric.samples]
    assert "0.5" in quantiles
    assert "0.95" in quantiles
    assert "0.99" in quantiles


def test_celery_metrics_collector_render_text():
    collector = CeleryMetricsCollector()
    text = collector.render_prometheus_text()

    assert "celery_queue_length" in text
    assert "celery_unacknowledged_tasks" in text
    assert "celery_task_execution_duration_seconds" in text
    assert "celery_active_workers" in text


@pytest.mark.django_db
def test_metrics_view_endpoint():
    client = APIClient()
    response = client.get("/api/v1/monitoring/metrics/")
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "celery_queue_length" in content
    assert "celery_unacknowledged_tasks" in content


def test_prometheus_alert_definitions():
    repo_root = Path(__file__).resolve().parents[3]
    alerts_file = repo_root / "infra" / "prometheus" / "alerts.yml"
    assert alerts_file.exists(), f"Missing alerts file at {alerts_file}"

    with open(alerts_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    groups = {g["name"]: g["rules"] for g in data.get("groups", [])}
    assert "celery_alerts" in groups

    rules = {r["alert"]: r for r in groups["celery_alerts"]}

    # 1. CeleryQueueLagHigh rule check
    assert "CeleryQueueLagHigh" in rules
    lag_rule = rules["CeleryQueueLagHigh"]
    assert "> 500" in lag_rule["expr"]
    assert lag_rule["for"] == "5m"
    assert lag_rule["labels"]["severity"] in ("warning", "critical")

    # 2. WorkerHeartbeatMissing rule check
    assert "WorkerHeartbeatMissing" in rules
    hb_rule = rules["WorkerHeartbeatMissing"]
    assert "celery_active_workers == 0" in hb_rule["expr"]
    assert hb_rule["labels"]["severity"] == "critical"


def test_grafana_dashboard_json_template():
    repo_root = Path(__file__).resolve().parents[3]
    dashboard_file = (
        repo_root / "infra" / "grafana" / "dashboards" / "celery_overview.json"
    )
    assert dashboard_file.exists(), f"Missing dashboard file at {dashboard_file}"

    with open(dashboard_file, "r", encoding="utf-8") as f:
        dashboard = json.load(f)

    assert dashboard["title"] == "Celery Overview"
    assert dashboard["uid"] == "celery-overview"

    # Verify panel targets query the expected metrics
    all_exprs = []
    for panel in dashboard.get("panels", []):
        for target in panel.get("targets", []):
            if "expr" in target:
                all_exprs.append(target["expr"])

    expr_text = " ".join(all_exprs)
    assert "celery_active_workers" in expr_text
    assert "celery_queue_length" in expr_text
    assert "celery_unacknowledged_tasks" in expr_text
    assert "celery_task_execution_duration_seconds" in expr_text
