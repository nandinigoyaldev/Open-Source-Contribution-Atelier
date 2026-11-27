import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.core.cache import cache

from apps.notifications.rate_limiter import _SLIDING_WINDOW_LUA, ChannelRateLimiter


class _FakeAtomicRedis:
    """Thread-safe in-memory Redis double implementing the sliding-window Lua script."""

    def __init__(self):
        self._lock = threading.Lock()
        self._zsets = {}
        self.eval_calls = 0

    def eval(self, script, numkeys, key, now_s, cutoff_s, max_req_s, ttl_ms_s, member):
        assert script == _SLIDING_WINDOW_LUA
        assert numkeys == 1
        now = float(now_s)
        cutoff = float(cutoff_s)
        max_req = int(max_req_s)

        with self._lock:
            self.eval_calls += 1
            zset = self._zsets.setdefault(key, {})
            # ZREMRANGEBYSCORE key -inf cutoff
            expired = [m for m, score in zset.items() if score <= cutoff]
            for m in expired:
                del zset[m]
            count = len(zset)
            if count >= max_req:
                return [0, count]
            zset[member] = now
            return [1, count + 1]


class TestChannelRateLimiter:
    def setup_method(self):
        cache.clear()

    def test_redis_sliding_window_enforces_limit_and_expires(self):
        fake_redis = _FakeAtomicRedis()
        t = [1000.0]

        with (
            patch(
                "apps.notifications.rate_limiter._get_redis_client",
                return_value=fake_redis,
            ),
            patch(
                "apps.notifications.rate_limiter.time.time", side_effect=lambda: t[0]
            ),
        ):
            assert ChannelRateLimiter.is_allowed(
                1, "email", max_requests=2, window_seconds=10
            ) == (True, 1)
            assert ChannelRateLimiter.is_allowed(
                1, "email", max_requests=2, window_seconds=10
            ) == (True, 2)
            assert ChannelRateLimiter.is_allowed(
                1, "email", max_requests=2, window_seconds=10
            ) == (False, 2)
            assert fake_redis.eval_calls == 3

            # Advance past window so previous entries expire
            t[0] = 1011.0
            assert ChannelRateLimiter.is_allowed(
                1, "email", max_requests=2, window_seconds=10
            ) == (True, 1)

    def test_redis_concurrent_requests_never_exceed_limit(self):
        fake_redis = _FakeAtomicRedis()
        max_requests = 5
        total_workers = 25
        barrier = threading.Barrier(total_workers)

        def worker():
            barrier.wait()
            return ChannelRateLimiter.is_allowed(
                42, "push", max_requests=max_requests, window_seconds=60
            )

        with (
            patch(
                "apps.notifications.rate_limiter._get_redis_client",
                return_value=fake_redis,
            ),
            ThreadPoolExecutor(max_workers=total_workers) as pool,
        ):
            results = list(pool.map(lambda _: worker(), range(total_workers)))

        allowed_count = sum(1 for allowed, _ in results if allowed)
        assert allowed_count == max_requests

    def test_fallback_concurrent_requests_never_exceed_limit(self):
        max_requests = 4
        total_workers = 20
        barrier = threading.Barrier(total_workers)

        def worker():
            barrier.wait()
            return ChannelRateLimiter.is_allowed(
                99, "sms", max_requests=max_requests, window_seconds=60
            )

        with (
            patch(
                "apps.notifications.rate_limiter._get_redis_client",
                return_value=None,
            ),
            ThreadPoolExecutor(max_workers=total_workers) as pool,
        ):
            results = list(pool.map(lambda _: worker(), range(total_workers)))

        allowed_count = sum(1 for allowed, _ in results if allowed)
        assert allowed_count == max_requests

    def test_fail_open_on_redis_error(self):
        class _BrokenRedis:
            def eval(self, *args, **kwargs):
                raise ConnectionError("Redis unavailable")

        with patch(
            "apps.notifications.rate_limiter._get_redis_client",
            return_value=_BrokenRedis(),
        ):
            allowed, count = ChannelRateLimiter.is_allowed(7, "webhook", max_requests=1)
            assert allowed is True
            assert count == 0

    def test_isolates_by_user_and_channel(self):
        with patch(
            "apps.notifications.rate_limiter._get_redis_client", return_value=None
        ):
            assert ChannelRateLimiter.is_allowed(1, "email", max_requests=1)[0] is True
            assert ChannelRateLimiter.is_allowed(1, "email", max_requests=1)[0] is False
            assert ChannelRateLimiter.is_allowed(1, "sms", max_requests=1)[0] is True
            assert ChannelRateLimiter.is_allowed(2, "email", max_requests=1)[0] is True
