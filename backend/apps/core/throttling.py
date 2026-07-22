import time
import uuid
import logging
from django.core.cache import cache
from rest_framework.throttling import SimpleRateThrottle

logger = logging.getLogger(__name__)


def get_redis_connection():
    try:
        from django_redis import get_redis_connection as get_redis

        return get_redis("default")
    except (ImportError, NotImplementedError):
        return None


class SlidingWindowThrottle(SimpleRateThrottle):
    """
    Rate throttle using sliding window algorithm via Redis sorted sets.
    """

    def allow_request(self, request, view):
        """
        Implement sliding window rate limiting.
        """
        if self.rate is None:
            return True

        self.key = self.get_cache_key(request, view)
        if self.key is None:
            return True

        self.history = []

        redis_client = get_redis_connection()
        if not redis_client:
            # Fallback to SimpleRateThrottle behavior if django-redis is not available
            return super().allow_request(request, view)

        self.now = time.time()

        # We want to know how many requests were made in the window
        cutoff = self.now - self.duration

        # Unique identifier for the request in the sorted set
        member_id = f"{self.now}:{uuid.uuid4().hex}"

        try:
            pipeline = redis_client.pipeline()
            # Remove requests outside the current window
            pipeline.zremrangebyscore(self.key, 0, cutoff)
            # Add the current request
            pipeline.zadd(self.key, {member_id: self.now})
            # Get the total count of requests in the window
            pipeline.zcard(self.key)
            # Set expiry so we don't leak memory for idle keys
            pipeline.expire(self.key, self.duration)
            results = pipeline.execute()

            count = results[2]

            if count > self.num_requests:
                # We must drop the one we just added because it's rejected
                redis_client.zrem(self.key, member_id)
                # Find the oldest score in the window to calculate Retry-After
                oldest = redis_client.zrange(self.key, 0, 0, withscores=True)
                if oldest:
                    self.oldest_score = oldest[0][1]
                else:
                    self.oldest_score = self.now
                return False

            return True
        except Exception as e:
            # If Redis goes down or there's an error, fail open or fallback
            logger.error(f"Redis rate limiting failed: {e}")
            return super().allow_request(request, view)

    def wait(self):
        """
        Returns the recommended number of seconds to wait before the next request.
        """
        if hasattr(self, "oldest_score"):
            wait_time = self.duration - (self.now - self.oldest_score)
            return max(1, int(wait_time))
        return super().wait()


class SlidingWindowAnonThrottle(SlidingWindowThrottle):
    scope = "anon"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class SlidingWindowUserThrottle(SlidingWindowThrottle):
    scope = "user"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {"scope": self.scope, "ident": ident}


class SlidingWindowScopedThrottle(SlidingWindowThrottle):
    scope_attr = "throttle_scope"

    def __init__(self):
        # Override SimpleRateThrottle init because ScopedRateThrottle does not use a fixed scope class attribute
        pass

    def allow_request(self, request, view):
        self.scope = getattr(view, self.scope_attr, None)
        if not self.scope:
            return True

        self.rate = self.get_rate()
        if not self.rate:
            return True

        self.num_requests, self.duration = self.parse_rate(self.rate)

        return super().allow_request(request, view)

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {"scope": self.scope, "ident": ident}
