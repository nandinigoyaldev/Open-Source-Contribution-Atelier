import logging
import time

import redis
from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


def get_redis_client():
    # Attempt to use raw redis client for ZSET operations (sliding window log).
    try:
        redis_url = getattr(settings, "REDIS_URL", None)
        if redis_url:
            return redis.from_url(
                redis_url,
                socket_connect_timeout=0.2,
                socket_timeout=0.2,
                decode_responses=True,
            )
    except Exception:
        pass
    return None


class RateLimitMiddleware(MiddlewareMixin):
    """
    Distributed rate limiting middleware using Redis (Sliding Window Log).
    """

    def __init__(self, get_response):
        super().__init__(get_response)
        self.auth_limit = getattr(settings, "API_RATE_LIMIT_AUTH", 100)
        self.anon_limit = getattr(settings, "API_RATE_LIMIT_ANON", 20)
        self.window = getattr(settings, "API_RATE_LIMIT_WINDOW", 60)
        self.redis_client = get_redis_client()

    def process_request(self, request):
        if getattr(settings, "DISABLE_RATE_LIMITING", False):
            return None

        if not request.path.startswith("/api/"):
            return None

        if request.path.startswith("/api/webhooks/"):
            return None

        # Bypass for admin, static, etc.
        if request.path.startswith(("/admin/", "/static/", "/health/", "/media/")):
            return None

        is_auth = hasattr(request, "user") and request.user.is_authenticated
        limit = self.auth_limit if is_auth else self.anon_limit

        if is_auth:
            identifier = f"user:{request.user.id}"
        else:
            x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
            if x_forwarded_for:
                ip = x_forwarded_for.split(",")[0].strip()
            else:
                ip = request.META.get("REMOTE_ADDR")
            identifier = f"ip:{ip}"

        cache_key = f"ratelimit:{identifier}"

        allowed, remaining = self._check_rate_limit(cache_key, limit, self.window)

        request._rate_limit_info = {
            "limit": limit,
            "remaining": remaining,
            "reset": self.window,
        }

        if not allowed:
            response = JsonResponse(
                {
                    "error": "Rate limit exceeded",
                    "message": "Too many requests. Please try again later.",
                    "remaining": 0,
                },
                status=429,
            )
            response["Retry-After"] = str(self.window)
            return response

        return None

    def process_response(self, request, response):
        if hasattr(request, "_rate_limit_info"):
            info = request._rate_limit_info
            response["X-RateLimit-Limit"] = str(info["limit"])
            response["X-RateLimit-Remaining"] = str(info["remaining"])
            response["X-RateLimit-Reset"] = str(int(time.time() + info["reset"]))

        return response

    def _check_rate_limit(self, key, limit, window):
        if self.redis_client:
            try:
                now = time.time()
                window_start = now - window

                pipe = self.redis_client.pipeline()
                pipe.zremrangebyscore(key, 0, window_start)
                pipe.zcard(key)
                pipe.zadd(key, {str(now): now})
                pipe.expire(key, window)
                results = pipe.execute()

                current_count = results[1]

                if current_count >= limit:
                    # Reject request, remove the just-added token
                    self.redis_client.zrem(key, str(now))
                    return False, 0

                remaining = max(0, limit - (current_count + 1))
                return True, remaining
            except Exception as e:
                logger.warning(f"Rate limit redis error, falling back to basic: {e}")
                pass

        # Fallback to basic fixed-window via Django cache
        try:
            current = cache.get(key, 0)
            if current >= limit:
                return False, 0
            if current == 0:
                cache.set(key, 1, window)
                return True, limit - 1
            else:
                current = cache.incr(key)
                return True, max(0, limit - current)
        except Exception as e:
            logger.error(f"Rate limiter failed open: {e}")
            return True, limit
