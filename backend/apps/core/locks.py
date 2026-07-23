"""
Redis distributed locks for Celery task synchronization.
"""

import logging
import time
import uuid
from contextlib import contextmanager
from typing import Optional, Any, Callable
from functools import wraps
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


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
            current_value = cache.get(self.lock_key)
            if current_value == self.lock_value:
                cache.delete(self.lock_key)
                self.acquired = False
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to release Redis lock {self.lock_key}: {e}")
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


def distributed_lock(lock_key: str, timeout: int = 60, retry_count: int = 3):
    """
    Decorator for distributed lock on Celery tasks.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            lock_key_with_args = lock_key
            if "{" in lock_key:
                lock_key_with_args = lock_key.format(*args, **kwargs)

            lock = RedisLock(lock_key_with_args, timeout, retry_count)
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
