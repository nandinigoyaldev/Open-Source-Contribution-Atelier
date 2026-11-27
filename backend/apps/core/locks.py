"""
Redis distributed locks for Celery task synchronization.
"""

import inspect
import logging
import os
import socket
import threading
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from typing import Any, Callable, Optional

from django.conf import settings
from django.core.cache import cache, caches
from django.core.cache.backends.redis import RedisCache

logger = logging.getLogger(__name__)

# Short lease for AutoRenewingLock. A dead worker's lock is gone after at most
# this many seconds, and a live one renews it every third of it (15s).
DEFAULT_LOCK_TTL = 45
_RENEW_THREAD_JOIN_TIMEOUT = 1.0
_AUTO_TOKEN_PREFIX = "autolock"

# Atomic compare-and-delete: only removes the key if its current value
# still matches the value this lock instance set when it acquired the
# lock. Prevents a TOCTOU race where the lock expires and is
# legitimately re-acquired by another process between a separate
# GET and DELETE call.
_RELEASE_LUA_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


# Atomic compare-and-expire: only the current owner can push the expiry out.
_RENEW_LUA_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("pexpire", KEYS[1], ARGV[2])
else
    return 0
end
"""


def _get_raw_redis_client():
    """Get the raw redis-py client underlying Django's cache, for atomic Lua execution."""
    from django_redis import get_redis_connection

    return get_redis_connection("default")


class RedisLock:
    """
    Redis distributed lock implementation.

    Usage:
        lock = RedisLock("task_name", timeout=60)
        with lock.acquire():
            # Critical section
            do_work()
    """

    def __init__(self, lock_key: str, timeout: int = 60, retry_count: int = 3):
        self.lock_key = f"celery_lock:{lock_key}"
        self.timeout = timeout
        self.retry_count = retry_count
        self.lock_value = str(uuid.uuid4())
        self.acquired = False

    def _acquire(self) -> bool:
        try:
            result = cache.add(self.lock_key, self.lock_value, self.timeout)
            if result:
                self.acquired = True
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to acquire Redis lock {self.lock_key}: {e}")
            return False

    def _release(self) -> bool:
        if not self.acquired:
            return False
        try:
            redis_client = _get_raw_redis_client()
            deleted = redis_client.eval(
                _RELEASE_LUA_SCRIPT, 1, self.lock_key, self.lock_value
            )
            self.acquired = False
            return bool(deleted)
        except Exception as e:
            logger.error(f"Failed to release Redis lock {self.lock_key}: {e}")
            # Fall back to the old non-atomic check-then-delete only if
            # the raw client / Lua eval genuinely isn't available (e.g.
            # a non-Redis cache backend in a dev/test environment) —
            # better than silently never releasing the lock at all.
            try:
                current_value = cache.get(self.lock_key)
                if current_value == self.lock_value:
                    cache.delete(self.lock_key)
                    return True
            except Exception as fallback_exc:
                logger.error(
                    f"Fallback release also failed for {self.lock_key}: {fallback_exc}"
                )
            return False

    @contextmanager
    def acquire(self):
        for attempt in range(self.retry_count):
            if self._acquire():
                try:
                    yield True
                    return
                finally:
                    self._release()
            else:
                delay = 2**attempt
                logger.debug(
                    f"Lock {self.lock_key} not acquired, attempt {attempt + 1}/{self.retry_count}"
                )
                time.sleep(delay)
        raise Exception(
            f"Could not acquire lock {self.lock_key} after {self.retry_count} attempts"
        )


def _redis_backend():
    """
    Return (client, make_key, encode) when the default cache is Redis, else None.

    cache.add() stores a prefixed key and a serialized value, so Lua scripts
    have to be given both in that same form.
    """
    backend: Any = caches["default"]
    if isinstance(backend, RedisCache):
        builtin: Any = backend._cache
        client = builtin.get_client(None, write=True)
        return client, backend.make_key, builtin._serializer.dumps

    django_redis_client = getattr(backend, "client", None)
    if django_redis_client is not None and hasattr(django_redis_client, "get_client"):
        return (
            django_redis_client.get_client(write=True),
            django_redis_client.make_key,
            django_redis_client.encode,
        )
    return None


def _extend_if_owner(key: str, token: str, seconds: float) -> bool:
    redis_backend = _redis_backend()
    if redis_backend is None:
        # Not atomic, only for the in-process cache used in dev and tests.
        if cache.get(key) != token:
            return False
        return bool(cache.touch(key, seconds))

    client, make_key, encode = redis_backend
    milliseconds = max(1, int(seconds * 1000))
    return bool(
        client.eval(
            _RENEW_LUA_SCRIPT, 1, str(make_key(key)), encode(token), milliseconds
        )
    )


def _delete_if_owner(key: str, token: str) -> bool:
    redis_backend = _redis_backend()
    if redis_backend is None:
        if cache.get(key) != token:
            return False
        return bool(cache.delete(key))

    client, make_key, encode = redis_backend
    return bool(client.eval(_RELEASE_LUA_SCRIPT, 1, str(make_key(key)), encode(token)))


class LockLostError(Exception):
    """The task no longer holds the lock it is running under."""


_current_lock: ContextVar[Optional["AutoRenewingLock"]] = ContextVar(
    "current_task_lock", default=None
)


def current_lock() -> Optional["AutoRenewingLock"]:
    """The AutoRenewingLock the running task is inside, if any."""
    return _current_lock.get()


class AutoRenewingLock(RedisLock):
    """
    Lock with a short TTL that a background thread keeps renewing.

    If the process dies, renewals stop and the key expires within ``ttl``
    seconds. If a renewal fails (Redis unreachable) or the key no longer holds
    our token, renewal stops and ``lost`` becomes True. The task is not
    interrupted, so long steps should call ``ensure_held()`` before writing.

    ``max_hold`` caps how long the lock can be held in total, so a hung but
    alive task cannot keep it forever. None means no cap.

    Usage:
        with AutoRenewingLock("reindex") as lock:
            build_index()
            lock.ensure_held()
            publish_index()
    """

    def __init__(
        self,
        lock_key: str,
        ttl: int = DEFAULT_LOCK_TTL,
        renew_interval: Optional[float] = None,
        retry_count: int = 3,
        max_hold: Optional[float] = None,
    ):
        if max_hold is not None:
            ttl = min(ttl, int(max_hold))
        if ttl < 1:
            raise ValueError("ttl and max_hold must be at least 1 second")
        if renew_interval is None:
            renew_interval = ttl / 3
        if not 0 < renew_interval < ttl:
            raise ValueError("renew_interval must be between 0 and ttl")

        super().__init__(lock_key, timeout=ttl, retry_count=retry_count)
        self.renew_interval = renew_interval
        self.max_hold = max_hold
        self._lost = threading.Event()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lease_deadline = 0.0
        self._hold_deadline = float("inf")

    @property
    def lost(self) -> bool:
        # The clock check covers a renewal call that hangs instead of failing.
        if (
            self.acquired
            and not self._lost.is_set()
            and time.monotonic() >= self._lease_deadline
        ):
            self._mark_lost("lease ran out before it was renewed")
        return self._lost.is_set()

    def ensure_held(self) -> None:
        if self.lost or not self.acquired:
            raise LockLostError(f"Lock {self.lock_key} is no longer held")

    def _mark_lost(self, reason: str) -> None:
        self._lost.set()
        logger.error(f"Lost Redis lock {self.lock_key}: {reason}")

    def _acquire(self) -> bool:
        if self.acquired:
            return False

        # The token records its owner so stranded locks can be recognised.
        hold_until = 0.0 if self.max_hold is None else time.time() + self.max_hold
        self.lock_value = ":".join(
            str(part)
            for part in (
                _AUTO_TOKEN_PREFIX,
                self.timeout,
                self.renew_interval,
                hold_until,
                socket.gethostname(),
                os.getpid(),
                uuid.uuid4().hex,
            )
        )
        # Deadlines are measured from before the request, to stay on the safe side.
        started = time.monotonic()
        if not super()._acquire():
            return False

        if self.max_hold is not None:
            self._hold_deadline = started + self.max_hold
        self._lease_deadline = min(started + self.timeout, self._hold_deadline)
        self._lost = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._renew_loop,
            args=(self._stop,),
            name=f"renew:{self.lock_key}",
            daemon=True,
        )
        self._thread.start()
        return True

    def _renew(self) -> bool:
        now = time.monotonic()
        if now >= self._lease_deadline:
            return False
        seconds = min(self.timeout, self._hold_deadline - now)
        if not _extend_if_owner(self.lock_key, self.lock_value, seconds):
            return False
        self._lease_deadline = now + seconds
        return True

    def _renew_loop(self, stop: threading.Event) -> None:
        while not stop.wait(self.renew_interval):
            if self._lost.is_set():
                return
            try:
                renewed = self._renew()
            except Exception as e:
                if not stop.is_set():
                    self._mark_lost(f"renewal failed, letting the key expire: {e}")
                return
            if not renewed:
                if not stop.is_set():
                    self._mark_lost("key expired or is owned by someone else")
                return

    def _release(self) -> bool:
        if not self.acquired:
            return False
        if self.lost:
            logger.warning(f"Lock {self.lock_key} was lost while the task ran")
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=_RENEW_THREAD_JOIN_TIMEOUT)
        self.acquired = False
        try:
            return _delete_if_owner(self.lock_key, self.lock_value)
        except Exception as e:
            logger.error(
                f"Failed to release Redis lock {self.lock_key}, "
                f"it will expire on its own: {e}"
            )
            return False

    @contextmanager
    def acquire(self):
        with super().acquire():
            token = _current_lock.set(self)
            try:
                yield True
            finally:
                _current_lock.reset(token)

    def __enter__(self) -> "AutoRenewingLock":
        self._context = self.acquire()
        self._context.__enter__()
        return self

    def __exit__(self, exc_type, exc, traceback):
        return self._context.__exit__(exc_type, exc, traceback)


def _process_is_alive(pid: int) -> bool:
    # os.kill(pid, 0) is only a harmless probe on POSIX.
    if os.name != "posix":
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def find_stranded_locks() -> list:
    """
    Auto-renewing locks whose owner looks dead or has stopped renewing.

    Only reports them. They expire on their own, and deleting one could take it
    away from a worker that is still running. Always empty without Redis, since
    an in-process cache does not survive a restart.
    """
    redis_backend = _redis_backend()
    if redis_backend is None:
        return []

    client, make_key, _ = redis_backend
    prefix = str(make_key(""))
    hostname = socket.gethostname()
    stranded = []
    for raw_key in client.scan_iter(match=f"{prefix}celery_lock:*", count=500):
        key = raw_key.decode("utf-8")[len(prefix) :]
        parts = str(cache.get(key)).split(":")
        if len(parts) != 7 or parts[0] != _AUTO_TOKEN_PREFIX:
            continue
        ttl, interval, hold_until = (float(part) for part in parts[1:4])
        host, pid = parts[4], int(parts[5])
        remaining = client.pttl(raw_key) / 1000
        if remaining <= 0:
            continue

        # A healthy owner never lets the TTL drop much below ttl - interval,
        # except when the lock is close to its max_hold.
        expected = ttl - interval
        if hold_until:
            expected = min(expected, hold_until - time.time())

        if host == hostname and not _process_is_alive(pid):
            reason = "owner process is gone"
        elif remaining < expected - interval / 3:
            reason = "renewal is overdue"
        else:
            continue

        stranded.append(
            {
                "key": key[len("celery_lock:") :],
                "host": host,
                "pid": pid,
                "ttl": remaining,
                "reason": reason,
            }
        )
    return stranded


def distributed_lock(lock_key: str, timeout: int = 60, retry_count: int = 3):
    """
    Decorator for distributed lock on Celery tasks.

    The lock is an AutoRenewingLock: its TTL is at most DEFAULT_LOCK_TTL and it
    is renewed while the task runs, for no longer than ``timeout`` seconds.
    """

    def decorator(func: Callable) -> Callable:
        signature = inspect.signature(func)

        @wraps(func)
        def wrapper(*args, **kwargs):
            lock_key_with_args = lock_key
            if "{" in lock_key:
                # Named placeholders must work for positional calls as well.
                named = signature.bind(*args, **kwargs).arguments
                lock_key_with_args = lock_key.format(*args, **{**named, **kwargs})

            lock = AutoRenewingLock(
                lock_key_with_args, retry_count=retry_count, max_hold=timeout
            )
            with lock.acquire():
                logger.info(f"Lock acquired for task: {lock_key_with_args}")
                result = func(*args, **kwargs)
                logger.info(f"Lock released for task: {lock_key_with_args}")
                return result

        return wrapper

    return decorator


class TaskLockManager:
    """
    Manager for task-level locking operations.
    """

    @staticmethod
    def is_locked(lock_key: str) -> bool:
        cache_key = f"celery_lock:{lock_key}"
        return cache.get(cache_key) is not None

    @staticmethod
    def get_lock_info(lock_key: str) -> Optional[dict]:
        cache_key = f"celery_lock:{lock_key}"
        value = cache.get(cache_key)
        if value:
            return {
                "key": lock_key,
                "value": value,
                "ttl": cache.ttl(cache_key),
            }
        return None

    @staticmethod
    def force_release(lock_key: str) -> bool:
        cache_key = f"celery_lock:{lock_key}"
        try:
            cache.delete(cache_key)
            logger.warning(f"Lock {lock_key} force released")
            return True
        except Exception as e:
            logger.error(f"Failed to force release lock {lock_key}: {e}")
            return False

    @staticmethod
    def get_all_locks() -> list:
        try:
            from django_redis import get_redis_connection

            redis_client = get_redis_connection("default")
            keys = redis_client.keys("celery_lock:*")
            return [k.decode("utf-8") for k in keys]
        except Exception as e:
            logger.error(f"Failed to get locks: {e}")
            return []
