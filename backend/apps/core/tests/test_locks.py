"""
Tests for the auto-renewing task lock.

Most tests use the in-memory test cache. The ones marked by the ``redis_cache``
fixture start a throwaway redis-server on a unix socket (no TCP port, so a
local Redis is never touched) and are skipped if the binary is not installed.
"""

import os
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from unittest import mock

import pytest
from celery.signals import worker_ready
from django.core.cache import cache
from django_q.signals import post_spawn

from apps.core import lock_signals, locks
from apps.core.locks import (
    AutoRenewingLock,
    LockLostError,
    TaskLockManager,
    current_lock,
    distributed_lock,
    find_stranded_locks,
)

REDIS_SERVER = shutil.which("redis-server")


def wait_until(condition, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.05)
    return False


def is_renewing(lock):
    return lock._thread is not None and lock._thread.is_alive()


def redis_client_and_key():
    backend = locks._redis_backend()
    assert backend is not None
    return backend[0], backend[1]


def short_lock(key, **kwargs):
    kwargs.setdefault("ttl", 1)
    kwargs.setdefault("renew_interval", 0.2)
    kwargs.setdefault("retry_count", 1)
    return AutoRenewingLock(key, **kwargs)


def simulate_worker_death(lock):
    """Stop the heartbeat without releasing, like a process that vanished."""
    lock._stop.set()
    lock._thread.join(timeout=2)


class RedisServer:
    def __init__(self):
        assert REDIS_SERVER
        # Unix socket paths are length limited, so avoid pytest's long tmp_path.
        self.directory = tempfile.mkdtemp(prefix="locks-")
        self.socket = os.path.join(self.directory, "r.sock")
        self.process = subprocess.Popen(
            [
                REDIS_SERVER,
                "--port",
                "0",
                "--unixsocket",
                self.socket,
                "--save",
                "",
                "--appendonly",
                "no",
                "--dir",
                self.directory,
            ],
            stdout=subprocess.DEVNULL,
        )
        if not wait_until(lambda: os.path.exists(self.socket)):
            self.stop()
            raise RuntimeError("throwaway redis-server did not start")

    def stop(self):
        self.process.kill()
        self.process.wait()
        shutil.rmtree(self.directory, ignore_errors=True)


@pytest.fixture(
    params=[
        "django.core.cache.backends.redis.RedisCache",
        "django_redis.cache.RedisCache",
    ],
    ids=["django-redis-builtin", "django-redis-package"],
)
def redis_cache(request, settings):
    if not REDIS_SERVER:
        pytest.skip("redis-server is not installed")
    server = RedisServer()
    original = settings.CACHES
    settings.CACHES = {
        "default": {
            "BACKEND": request.param,
            "LOCATION": f"unix://{server.socket}",
        }
    }
    yield server
    settings.CACHES = original
    server.stop()


# ── In-memory cache ──────────────────────────────────────────────────────


def test_lock_is_renewed_past_its_ttl_and_released():
    with short_lock("renewed") as lock:
        time.sleep(1.6)
        assert cache.get(lock.lock_key) == lock.lock_value
        assert not lock.lost
        lock.ensure_held()

    assert cache.get(lock.lock_key) is None
    assert not is_renewing(lock)


def test_default_ttl_and_renew_interval():
    lock = AutoRenewingLock("defaults")

    assert lock.timeout == 45
    assert lock.renew_interval == 15


@pytest.mark.parametrize(
    "kwargs",
    [
        {"ttl": 0},
        {"max_hold": 0},
        {"renew_interval": 0},
        {"ttl": 5, "renew_interval": 5},
    ],
)
def test_invalid_timings_are_rejected(kwargs):
    with pytest.raises(ValueError):
        AutoRenewingLock("invalid", **kwargs)


def test_held_lock_cannot_be_taken_and_failed_attempt_keeps_owner(monkeypatch):
    monkeypatch.setattr(locks.time, "sleep", lambda seconds: None)
    with short_lock("busy") as lock:
        with pytest.raises(Exception, match="Could not acquire lock"):
            with short_lock("busy"):
                pass
        # Nested use of the same instance must not overwrite its token.
        with pytest.raises(Exception, match="Could not acquire lock"):
            with lock.acquire():
                pass
        assert cache.get(lock.lock_key) == lock.lock_value


def test_dead_worker_lock_expires_and_can_be_taken_again():
    dead = short_lock("dead-worker")
    assert dead._acquire()
    simulate_worker_death(dead)
    assert cache.get(dead.lock_key) is not None

    assert wait_until(lambda: cache.get(dead.lock_key) is None, timeout=3)
    assert dead.lost
    with short_lock("dead-worker") as retry:
        retry.ensure_held()


def test_redis_down_during_renewal_stops_renewing_and_lets_key_expire():
    with mock.patch.object(
        locks, "_extend_if_owner", side_effect=ConnectionError("redis down")
    ) as extend:
        with short_lock("redis-down") as lock:
            assert wait_until(lambda: lock.lost)
            with pytest.raises(LockLostError):
                lock.ensure_held()
            assert wait_until(lambda: cache.get(lock.lock_key) is None, timeout=3)

    assert extend.call_count == 1
    assert not is_renewing(lock)


def test_release_does_not_raise_while_redis_is_down():
    down = ConnectionError("redis down")
    with mock.patch.object(locks, "_delete_if_owner", side_effect=down):
        with short_lock("release-down") as lock:
            pass

    assert not lock.acquired
    assert wait_until(lambda: cache.get(lock.lock_key) is None, timeout=3)


def test_hung_renewal_is_flagged_when_the_lease_runs_out():
    unblock = threading.Event()

    def hang(*args):
        unblock.wait(10)
        return True

    with mock.patch.object(locks, "_extend_if_owner", side_effect=hang):
        started = time.monotonic()
        with short_lock("hung") as lock:
            assert wait_until(lambda: lock.lost, timeout=3)
            assert time.monotonic() - started < 3
            unblock.set()
    assert not is_renewing(lock)


def test_lock_taken_over_by_someone_else_is_not_extended_or_deleted():
    with short_lock("stolen") as lock:
        cache.set(lock.lock_key, "new-owner", 30)
        assert wait_until(lambda: lock.lost)

    assert cache.get(lock.lock_key) == "new-owner"


def test_force_release_flags_the_running_task():
    with short_lock("forced") as lock:
        assert TaskLockManager.force_release("forced")
        assert wait_until(lambda: lock.lost)


def test_max_hold_stops_renewal_for_a_task_that_never_finishes():
    with short_lock("capped", max_hold=1.5) as lock:
        time.sleep(1.2)
        assert not lock.lost
        assert wait_until(lambda: cache.get(lock.lock_key) is None, timeout=2)
        assert lock.lost


def test_distributed_lock_formats_key_and_exposes_the_lock():
    seen = []

    @distributed_lock("report:{user_id}", timeout=120)
    def task(user_id):
        lock = current_lock()
        assert lock is not None
        seen.append((lock.lock_key, lock.timeout, lock.max_hold))
        assert TaskLockManager.is_locked(f"report:{user_id}")
        return user_id

    assert task(7) == 7
    assert task(user_id=8) == 8
    assert seen == [
        ("celery_lock:report:7", 45, 120),
        ("celery_lock:report:8", 45, 120),
    ]
    assert not TaskLockManager.is_locked("report:7")
    assert current_lock() is None


def test_distributed_lock_releases_when_the_task_raises():
    @distributed_lock("failing", timeout=10)
    def task():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        task()

    assert not TaskLockManager.is_locked("failing")
    assert current_lock() is None


def test_stranded_lock_check_is_empty_without_redis():
    with short_lock("in-memory"):
        assert find_stranded_locks() == []


@pytest.mark.parametrize("signal_", [worker_ready, post_spawn])
def test_worker_start_logs_stranded_locks(signal_):
    stranded = {
        "key": "report:7",
        "host": "worker-1",
        "pid": 42,
        "ttl": 30.0,
        "reason": "owner process is gone",
    }
    with (
        mock.patch.object(lock_signals, "find_stranded_locks", return_value=[stranded]),
        mock.patch.object(lock_signals.logger, "warning") as warning,
    ):
        signal_.send(sender="test", proc_name="worker")

    assert "report:7" in warning.call_args.args[0]


def test_worker_start_survives_redis_being_down():
    with mock.patch.object(
        lock_signals, "find_stranded_locks", side_effect=ConnectionError("down")
    ):
        lock_signals.report_stranded_locks()


# ── Real Redis ───────────────────────────────────────────────────────────


def test_redis_renewal_and_release(redis_cache):
    client, make_key = redis_client_and_key()

    with short_lock("real") as lock:
        time.sleep(1.6)
        assert cache.get(lock.lock_key) == lock.lock_value
        assert 0 < client.pttl(str(make_key(lock.lock_key))) <= 1000
        assert not lock.lost
        assert find_stranded_locks() == []

    assert cache.get(lock.lock_key) is None


def test_redis_renewal_only_extends_its_own_token(redis_cache):
    client, make_key = redis_client_and_key()

    with short_lock("real-stolen") as lock:
        cache.set(lock.lock_key, "new-owner", 30)
        assert wait_until(lambda: lock.lost)

    assert cache.get(lock.lock_key) == "new-owner"
    assert client.pttl(str(make_key(lock.lock_key))) > 20000


@pytest.mark.skipif(not hasattr(os, "fork"), reason="needs os.fork")
def test_redis_worker_killed_mid_task(redis_cache):
    read_end, write_end = os.pipe()
    pid = os.fork()
    if pid == 0:
        try:
            with short_lock("killed", ttl=2):
                os.write(write_end, b"1")
                time.sleep(30)
        finally:
            os._exit(1)

    os.close(write_end)
    try:
        assert os.read(read_end, 1) == b"1"
        # Alive past the TTL, so the child really is renewing.
        time.sleep(2.5)
        assert TaskLockManager.is_locked("killed")
        assert find_stranded_locks() == []
    finally:
        os.close(read_end)
        os.kill(pid, signal.SIGKILL)
        os.waitpid(pid, 0)

    [stranded] = find_stranded_locks()
    assert stranded["key"] == "killed"
    assert stranded["pid"] == pid
    assert stranded["reason"] == "owner process is gone"
    assert 0 < stranded["ttl"] <= 2

    assert wait_until(lambda: not TaskLockManager.is_locked("killed"), timeout=3)
    with short_lock("killed") as retry:
        retry.ensure_held()


def test_redis_overdue_renewal_is_reported(redis_cache):
    lock = short_lock("overdue", ttl=3, renew_interval=0.6)
    assert lock._acquire()
    simulate_worker_death(lock)

    # Our own process is alive, so only the missed renewals give it away.
    assert wait_until(lambda: find_stranded_locks() != [], timeout=2.5)
    [stranded] = find_stranded_locks()
    assert stranded["reason"] == "renewal is overdue"


def test_redis_server_going_down_does_not_block_the_task(redis_cache):
    started = time.monotonic()
    with short_lock("outage") as lock:
        redis_cache.stop()
        assert wait_until(lambda: lock.lost)

    assert time.monotonic() - started < 5
    assert not lock.acquired
    assert not is_renewing(lock)
