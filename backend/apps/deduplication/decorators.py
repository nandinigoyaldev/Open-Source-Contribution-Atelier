"""
Decorators for request deduplication.
"""

import functools
import hashlib
import json
import time
from typing import Dict, Any, Optional
from django.core.cache import cache
from django.http import JsonResponse
import logging

logger = logging.getLogger(__name__)


class RequestDeduplicator:
    """
    Class-based request deduplication decorator.
    """

    def __init__(self, ttl: int = 60, key_prefix: str = "dedup"):
        self.ttl = ttl
        self.key_prefix = key_prefix

    def _get_cache_key(self, func_name: str, args, kwargs) -> str:
        """Generate cache key for function call."""
        # Create a unique key from function name and arguments
        key_parts = [func_name]

        # Add positional args
        for arg in args:
            try:
                key_parts.append(str(arg))
            except:
                key_parts.append(str(type(arg)))

        # Add keyword args (sorted for consistency)
        for k, v in sorted(kwargs.items()):
            try:
                key_parts.append(f"{k}:{v}")
            except:
                key_parts.append(f"{k}:{type(v)}")

        key_string = "|".join(key_parts)
        return f"{self.key_prefix}:{hashlib.md5(key_string.encode()).hexdigest()}"

    def __call__(self, func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = self._get_cache_key(func.__name__, args, kwargs)
            lock_key = f"{cache_key}:lock"

            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_result

            # Try to acquire lock (prevent duplicate execution)
            lock_acquired = cache.add(lock_key, "locked", timeout=5)

            if not lock_acquired:
                # Another instance is executing, wait and retry
                max_wait = 5  # seconds
                start_time = time.time()

                while time.time() - start_time < max_wait:
                    cached_result = cache.get(cache_key)
                    if cached_result is not None:
                        logger.debug(f"Waited and got result for {func.__name__}")
                        return cached_result
                    time.sleep(0.1)

                # Fallback: execute anyway
                logger.warning(f"Timeout waiting for {func.__name__}, executing")
                result = func(*args, **kwargs)
            else:
                # Execute function
                try:
                    result = func(*args, **kwargs)
                    # Cache result
                    cache.set(cache_key, result, self.ttl)
                    logger.debug(f"Cached result for {func.__name__}")
                finally:
                    # Release lock
                    cache.delete(lock_key)

            return result

        return wrapper


def deduplicate_request(ttl: int = 60, key_prefix: str = "dedup"):
    """
    Decorator to deduplicate function calls.

    Usage:
        @deduplicate_request(ttl=30)
        def expensive_operation(user_id):
            # This will be executed only once for concurrent calls
            return result
    """
    return RequestDeduplicator(ttl=ttl, key_prefix=key_prefix)


def cache_result(ttl: int = 60, key_prefix: str = "cache"):
    """
    Decorator to cache function results.

    Usage:
        @cache_result(ttl=300)
        def get_user_profile(user_id):
            # Result will be cached for 5 minutes
            return profile
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            deduplicator = RequestDeduplicator(ttl=ttl, key_prefix=key_prefix)
            cache_key = deduplicator._get_cache_key(func.__name__, args, kwargs)

            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result

            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result

        return wrapper

    return decorator
