from __future__ import annotations

import logging
import threading
import time
import uuid

from django.core.cache import cache

logger = logging.getLogger(__name__)

# Default limits: max 10 notifications per (user, channel) per 60 seconds
DEFAULT_CHANNEL_LIMITS = {
    "in_app": 30,
    "email": 10,
    "push": 15,
    "sms": 5,
    "webhook": 20,
    "slack": 20,
}

# Atomic sliding-window check-and-insert using a Redis Sorted Set.
# Returns {allowed (0|1), current_count}.
_SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local cutoff = tonumber(ARGV[2])
local max_req = tonumber(ARGV[3])
local ttl_ms = tonumber(ARGV[4])
local member = ARGV[5]

redis.call("ZREMRANGEBYSCORE", key, "-inf", cutoff)
local count = redis.call("ZCARD", key)
if count >= max_req then
    return {0, count}
end
redis.call("ZADD", key, now, member)
redis.call("PEXPIRE", key, ttl_ms)
return {1, count + 1}
"""

_fallback_lock = threading.Lock()


def _get_redis_client():
    """Return a Redis client if the default cache backend is Redis-backed."""
    try:
        from django_redis import get_redis_connection  # type: ignore

        return get_redis_connection("default")
    except (ImportError, NotImplementedError, AttributeError) as exc:
        logger.debug("django_redis default connection unavailable: %s", exc)

    client = getattr(cache, "client", None)
    if client is not None and hasattr(client, "get_client"):
        try:
            return client.get_client(write=True)
        except (NotImplementedError, AttributeError, ConnectionError) as exc:
            logger.debug("Cache client.get_client unavailable: %s", exc)
    return None


class ChannelRateLimiter:
    """
    Atomic sliding-window rate limiter for (user, channel).

    Uses a Redis Sorted Set Lua script when Redis is available, with a
    thread-safe Django cache fallback for non-Redis backends (e.g. LocMemCache).
    """

    @classmethod
    def _is_allowed_redis(
        cls,
        redis_client,
        key: str,
        now: float,
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, int]:
        cutoff = now - window_seconds
        ttl_ms = max(1, int(window_seconds * 2 * 1000))
        member = f"{now}:{uuid.uuid4().hex}"
        result = redis_client.eval(
            _SLIDING_WINDOW_LUA,
            1,
            key,
            str(now),
            str(cutoff),
            str(max_requests),
            str(ttl_ms),
            member,
        )
        allowed = bool(int(result[0]))
        count = int(result[1])
        return allowed, count

    @classmethod
    def _is_allowed_fallback(
        cls,
        key: str,
        now: float,
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, int]:
        cutoff = now - window_seconds
        with _fallback_lock:
            timestamps = cache.get(key, [])
            valid_timestamps = [t for t in timestamps if t > cutoff]
            if len(valid_timestamps) >= max_requests:
                return False, len(valid_timestamps)
            valid_timestamps.append(now)
            cache.set(key, valid_timestamps, timeout=window_seconds * 2)
            return True, len(valid_timestamps)

    @classmethod
    def is_allowed(
        cls,
        user_id: int,
        channel_id: str,
        max_requests: int | None = None,
        window_seconds: int = 60,
    ) -> tuple[bool, int]:
        if max_requests is None:
            max_requests = DEFAULT_CHANNEL_LIMITS.get(channel_id, 10)

        now = time.time()
        key = f"notif_ratelimit:{user_id}:{channel_id}"

        try:
            redis_client = _get_redis_client()
            if redis_client is not None:
                allowed, count = cls._is_allowed_redis(
                    redis_client, key, now, max_requests, window_seconds
                )
            else:
                allowed, count = cls._is_allowed_fallback(
                    key, now, max_requests, window_seconds
                )

            if not allowed:
                logger.warning(
                    "Rate limit exceeded for user %s on channel %s (%d/%d in %ds)",
                    user_id,
                    channel_id,
                    count,
                    max_requests,
                    window_seconds,
                )
            return allowed, count
        except (
            Exception
        ) as exc:  # noqa: BLE001 - fail open on any cache backend failure
            logger.warning("Error in ChannelRateLimiter for user %s: %s", user_id, exc)
            return True, 0  # Fail open if cache fails
