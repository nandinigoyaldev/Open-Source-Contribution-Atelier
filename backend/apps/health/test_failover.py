# pyright: reportAttributeAccessIssue=false
"""
Failure injection for realtime and worker failover (docs/DISASTER_RECOVERY.md).

Nothing here needs a real Redis, broker or worker. The "dead Redis" is a channel layer
pointed at a closed local port, so the failures are real connection errors, not mocks.
Run:  pytest apps/health/test_failover.py --no-migrations
"""

import asyncio
import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from channels.db import database_sync_to_async
from channels.layers import InMemoryChannelLayer, channel_layers
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken

from apps.core import resilient_channel_layer as rcl
from apps.core.resilient_channel_layer import ResilientChannelLayer
from apps.health import failover
from apps.monitoring import job_ops
from apps.monitoring.models import TaskRun
from apps.monitoring.tasks import reap_stuck_task_runs, requeue_orphaned_runs

DEAD_REDIS = "redis://127.0.0.1:1/0"
User = get_user_model()


def make_layer(hosts=(DEAD_REDIS,)) -> ResilientChannelLayer:
    return ResilientChannelLayer(hosts=list(hosts), capacity=10, expiry=5)


@pytest.fixture(autouse=True)
def _clean_cache():
    cache.clear()
    yield
    cache.clear()


# --- realtime: dead Redis, degrade, fail back ----------------------------------------


@pytest.mark.asyncio
async def test_dead_redis_degrades_and_realtime_keeps_working_in_process():
    layer = make_layer()
    assert layer.status()["state"] == "ready"

    # The first operation hits the closed port, switches to the fallback and then
    # succeeds on it: the caller never sees the outage.
    await layer.group_add("room", "chan-1")
    assert layer.degraded is True
    assert layer.status()["state"] == "degraded"
    assert layer.status()["backend"] == "InMemoryChannelLayer"

    await layer.group_send("room", {"type": "chat.message", "n": 1})
    message = await asyncio.wait_for(layer.receive("chan-1"), timeout=2)
    assert message == {"type": "chat.message", "n": 1}


@pytest.mark.asyncio
async def test_failback_is_refused_while_connections_are_on_the_fallback():
    layer = make_layer()
    await layer.group_add("room", "chan-1")  # degrades, chan-1 lives on the fallback
    assert layer.degraded

    # Redis is back, but chan-1 would stop receiving if we switched now.
    with patch.object(layer, "_ping_primary", return_value=True):
        assert await layer.try_failback(force=True) is False
    assert layer.degraded is True
    status = layer.status()
    assert status["primary_recovered"] is True
    assert status["fallback_subscribers"] is True

    # Once the last client has gone, the next probe moves the process back.
    await layer.group_discard("room", "chan-1")
    layer._primary = InMemoryChannelLayer()  # stands in for the restored Redis
    with patch.object(layer, "_ping_primary", return_value=True):
        assert await layer.try_failback(force=True) is True
    assert layer.degraded is False
    assert layer.status()["state"] == "ready"
    await layer.group_add("room", "chan-2")
    await layer.group_send("room", {"type": "x"})
    assert await asyncio.wait_for(layer.receive("chan-2"), timeout=2) == {"type": "x"}


@pytest.mark.asyncio
async def test_failback_probe_is_rate_limited_and_stays_degraded_while_redis_is_down():
    layer = make_layer()
    await layer.group_add("room", "chan-1")
    await layer.group_discard("room", "chan-1")

    pings = []

    async def dead_ping():
        pings.append(1)
        return False

    with patch.object(layer, "_ping_primary", side_effect=dead_ping):
        assert await layer.try_failback(force=True) is False
        # Ordinary traffic triggers probes too, but not more often than the interval.
        await layer.group_add("room", "chan-1")
        await layer.group_add("room", "chan-1")
    assert len(pings) == 1
    assert layer.degraded is True
    assert layer.status()["primary_recovered"] is False


@pytest.mark.asyncio
async def test_real_ping_against_dead_port_is_false_and_fast():
    layer = make_layer()
    assert await asyncio.wait_for(layer._ping_primary(), timeout=3) is False


# --- realtime: client reconnect with a cursor, no duplicates ------------------------


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_chat_client_reconnects_with_cursor_after_redis_outage(settings):
    """
    A chat client is connected, Redis dies, the process degrades, the client's socket
    drops and it reconnects to another instance with the last message id it saw. It
    gets exactly the messages it missed, once each.
    """
    from apps.chat.models import Message
    from config.asgi import application

    settings.CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "apps.core.resilient_channel_layer.ResilientChannelLayer",
            "CONFIG": {"hosts": [DEAD_REDIS], "capacity": 10, "expiry": 5},
        }
    }
    channel_layers.backends = {}  # build the layer from the settings above

    user = await database_sync_to_async(User.objects.create_user)(
        username="drill-user", password="pw-for-drill-1"
    )
    token = str(AccessToken.for_user(user))
    headers = [(b"origin", b"http://localhost")]
    url = f"/ws/chat/drill/?token={token}"

    first = WebsocketCommunicator(application, url, headers=headers)
    assert (await first.connect())[0]
    for _ in range(2):  # connection_established, presence_sync
        await first.receive_json_from()

    await first.send_json_to({"action": "send_message", "message": "before outage"})
    seen = []
    while len(seen) < 1:
        event = await first.receive_json_from()
        if event["type"] == "new_message":
            seen.append(event["id"])
    layer = channel_layers["default"]
    assert layer.degraded is True  # the group_add in connect() already hit dead Redis

    # Socket drops with the instance. While the client is away, two more messages land
    # (sent by other users on the surviving instance).
    await first.disconnect()
    other = await database_sync_to_async(User.objects.create_user)(
        username="other", password="pw-for-drill-2"
    )
    for text in ("missed 1", "missed 2"):
        await database_sync_to_async(Message.objects.create)(
            room_id="drill", user=other, content=text
        )

    cursor = max(seen)
    second = WebsocketCommunicator(
        application, f"{url}&since_id={cursor}", headers=headers
    )
    assert (await second.connect())[0]
    established = await second.receive_json_from()
    assert established["type"] == "connection_established"
    sync = await second.receive_json_from()
    assert sync["type"] == "history_sync"
    contents = [m["content"] for m in sync["messages"]]
    ids = [m["id"] for m in sync["messages"]]
    assert contents == ["missed 1", "missed 2"]
    assert all(i > cursor for i in ids)
    assert len(set(ids)) == len(ids)
    assert sync["resync_required"] is False
    await second.disconnect()


# --- workers: dead worker, lease expiry, requeue exactly once ------------------------


@pytest.fixture
def broker():
    with patch("apps.monitoring.job_ops.current_app") as app:
        app.send_task.return_value = MagicMock(id="replacement-task")
        app.tasks.get.return_value = MagicMock(failover_requeue=True)
        yield app


def started_run(task_id="dead-1", **fields):
    fields.setdefault("task_name", "apps.demo.tasks.rebuild_index")
    fields.setdefault("lease_expires_at", timezone.now() - timedelta(seconds=5))
    return TaskRun.objects.create(task_id=task_id, status="STARTED", **fields)


@pytest.mark.django_db
def test_dead_worker_run_is_marked_stuck_then_requeued_exactly_once(broker):
    run = started_run()

    # The worker died mid task: nothing sends a heartbeat. One reaper pass notices.
    assert reap_stuck_task_runs() == {"marked_stuck": 1}
    run.refresh_from_db()
    assert run.status == "STUCK"

    first = requeue_orphaned_runs()
    assert first["requeued"] == 1
    # A second pass, or a second beat process running at the same moment, does nothing.
    second = requeue_orphaned_runs()
    assert second["requeued"] == 0

    assert broker.send_task.call_count == 1
    broker.send_task.assert_called_with("apps.demo.tasks.rebuild_index")
    run.refresh_from_db()
    assert run.status == "RETRY"
    assert run.retry_count == 1


@pytest.mark.django_db
def test_run_that_took_a_heartbeat_in_time_is_not_requeued(broker):
    run = started_run(lease_expires_at=timezone.now() - timedelta(seconds=5))
    assert job_ops.touch_heartbeat(run.task_id, lease_seconds=300) is True

    assert reap_stuck_task_runs() == {"marked_stuck": 0}
    assert requeue_orphaned_runs()["requeued"] == 0
    broker.send_task.assert_not_called()


@pytest.mark.django_db
def test_task_that_did_not_opt_in_or_has_arguments_is_left_for_an_operator(broker):
    broker.tasks.get.return_value = MagicMock(failover_requeue=False)
    TaskRun.objects.create(task_id="a", task_name="not.opted.in", status="STUCK")
    broker.tasks.get.side_effect = lambda name: (
        MagicMock(failover_requeue=True)
        if name == "opted.in.with.args"
        else MagicMock(failover_requeue=False)
    )
    TaskRun.objects.create(
        task_id="b",
        task_name="opted.in.with.args",
        status="STUCK",
        args_summary="args=(42,)",
    )

    counts = requeue_orphaned_runs()
    assert counts["requeued"] == 0
    assert counts["skipped_unsafe"] == 2
    broker.send_task.assert_not_called()


@pytest.mark.django_db
def test_task_listed_in_settings_is_requeued(broker, settings):
    broker.tasks.get.return_value = None
    settings.FAILOVER_REQUEUE_TASKS = ("apps.demo.tasks.rebuild_index",)
    TaskRun.objects.create(
        task_id="c", task_name="apps.demo.tasks.rebuild_index", status="STUCK"
    )
    assert requeue_orphaned_runs()["requeued"] == 1


@pytest.mark.django_db
def test_task_that_keeps_dying_stops_after_the_attempt_cap(broker, settings):
    settings.FAILOVER_REQUEUE_MAX_ATTEMPTS = 2
    for attempt in range(4):
        TaskRun.objects.create(
            task_id=f"loop-{attempt}",
            task_name="apps.demo.tasks.rebuild_index",
            status="STUCK",
        )
        requeue_orphaned_runs()

    assert broker.send_task.call_count == 2
    left = TaskRun.objects.filter(status="STUCK").count()
    assert left == 2  # handed to an operator, not retried forever


@pytest.mark.django_db
def test_broker_outage_during_requeue_loses_nothing(broker):
    TaskRun.objects.create(
        task_id="d", task_name="apps.demo.tasks.rebuild_index", status="STUCK"
    )
    broker.send_task.side_effect = ConnectionError("broker down")

    assert requeue_orphaned_runs()["broker_unavailable"] == 1
    assert TaskRun.objects.get(task_id="d").status == "STUCK"

    broker.send_task.side_effect = None
    assert requeue_orphaned_runs()["requeued"] == 1


# --- health: ready, degraded, unavailable ---------------------------------------------


@pytest.mark.django_db
def test_everything_up_is_ready_and_answers_200(client, settings):
    settings.CHANNEL_LAYER_BACKEND = "inmemory:forced"  # single process by design
    response = client.get("/health/failover/")
    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "ready"
    assert set(body["dependencies"]) == {"database", "cache", "realtime", "workers"}
    assert all(d["state"] == "ready" for d in body["dependencies"].values())


@pytest.mark.django_db
def test_stuck_and_old_queue_make_workers_degraded_then_unavailable(client, settings):
    settings.CHANNEL_LAYER_BACKEND = "inmemory:forced"
    TaskRun.objects.create(task_id="s", task_name="t", status="STUCK")
    body = client.get("/health/failover/").json()
    assert body["dependencies"]["workers"]["state"] == "degraded"
    assert body["status"] == "degraded"

    TaskRun.objects.all().delete()
    TaskRun.objects.create(
        task_id="p",
        task_name="t",
        status="PENDING",
        queued_at=timezone.now()
        - timedelta(seconds=settings.FAILOVER_QUEUE_AGE_UNAVAILABLE_SECONDS + 5),
    )
    response = client.get("/health/failover/")
    body = response.json()
    assert body["dependencies"]["workers"]["state"] == "unavailable"
    # Workers are not critical: serving continues, the instance stays in rotation.
    assert body["status"] == "degraded"
    assert response.status_code == 200


@pytest.mark.django_db
def test_degraded_channel_layer_is_reported_with_the_recovery_action(client):
    layer = make_layer()
    asyncio.run(layer.group_add("room", "chan-1"))
    with (
        patch("channels.layers.get_channel_layer", return_value=layer),
        patch.object(layer, "_ping_primary", return_value=True),
    ):
        body = client.get("/health/failover/").json()
    realtime = body["dependencies"]["realtime"]
    assert realtime["state"] == "degraded"
    assert realtime["primary_recovered"] is True
    assert "recycle" in realtime["action"]
    assert body["status"] == "degraded"


@pytest.mark.django_db
def test_database_down_is_unavailable_and_answers_503(client):
    with patch("apps.health.failover.connection") as conn:
        conn.cursor.side_effect = RuntimeError("secret-host.internal refused")
        response = client.get("/health/failover/")
    body = response.json()
    assert response.status_code == 503
    assert body["status"] == "unavailable"
    assert body["dependencies"]["database"]["state"] == "unavailable"
    # Only the exception class is reported, never its text (it can carry hostnames).
    assert body["dependencies"]["database"]["error"] == "RuntimeError"
    assert "secret-host" not in json.dumps(body)


@pytest.mark.django_db
def test_cache_down_degrades_but_does_not_take_the_instance_out(client, settings):
    settings.CHANNEL_LAYER_BACKEND = "inmemory:forced"
    with patch("apps.health.failover.cache") as broken:
        broken.set.side_effect = ConnectionError("redis down")
        response = client.get("/health/failover/")
    body = response.json()
    assert body["dependencies"]["cache"]["state"] == "unavailable"
    assert body["status"] == "degraded"
    assert response.status_code == 200


@pytest.mark.django_db
def test_critical_set_is_configurable(client, settings):
    settings.FAILOVER_CRITICAL_DEPENDENCIES = ("database", "cache")
    with patch("apps.health.failover.cache") as broken:
        broken.set.side_effect = ConnectionError("redis down")
        response = client.get("/health/failover/")
    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"


def test_worst_picks_the_most_severe_state():
    assert failover.worst([failover.READY, failover.DEGRADED]) == failover.DEGRADED
    assert failover.worst([failover.DEGRADED, failover.UNAVAILABLE]) == (
        failover.UNAVAILABLE
    )
    assert failover.worst([]) == failover.READY


# --- recovery objectives --------------------------------------------------------------


@pytest.mark.django_db
def test_stated_objectives_match_the_code(settings):
    """The numbers in the runbook come from here; the code must actually meet them."""
    objectives = failover.RECOVERY_OBJECTIVES
    # Failback probes are no more than the promised interval apart.
    assert rcl.FAILBACK_PROBE_INTERVAL <= objectives["realtime_failback_probe_seconds"]
    # The beat schedule runs the reaper and the requeue at the promised cadence.
    from config.settings import CELERY_BEAT_SCHEDULE

    for entry in ("reap-stuck-task-runs", "requeue-orphaned-task-runs"):
        assert (
            CELERY_BEAT_SCHEDULE[entry]["schedule"]
            <= objectives["worker_reap_interval_seconds"]
        )
