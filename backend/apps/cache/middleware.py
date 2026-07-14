"""
Middleware for cache control headers.
"""

from django.utils.deprecation import MiddlewareMixin
from django.utils.cache import patch_cache_control, get_max_age
from django.http import JsonResponse
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    A simple Redis/Cache-backed Rate Limiter.
    Limits to 100 requests per minute per key.
    """

    def __init__(self, limit=100, window=60):
        self.limit = limit
        self.window = window

    def is_allowed(self, key):
        cache_key = f"ratelimit_{key}"
        try:
            current = cache.get(cache_key, 0)
            if current >= self.limit:
                return False
            if current == 0:
                cache.set(cache_key, 1, self.window)
            else:
                try:
                    cache.incr(cache_key)
                except ValueError:
                    cache.set(cache_key, 1, self.window)
            return True
        except Exception:
            # Fail open if cache is unreachable
            return True

    def get_remaining(self, key):
        cache_key = f"ratelimit_{key}"
        try:
            current = cache.get(cache_key, 0)
            return max(0, self.limit - current)
        except Exception:
            return self.limit


class CacheControlMiddleware(MiddlewareMixin):
    """
    Middleware for setting cache control headers.
    """

    def process_response(self, request, response):
        """
        Add cache control headers to responses.
        """
        # Skip for authenticated requests (private)
        if request.user.is_authenticated:
            patch_cache_control(response, private=True, max_age=60)
            return response

        # Public caching for static-like endpoints
        if request.path.startswith("/api/content/"):
            patch_cache_control(response, public=True, max_age=300)
        elif request.path.startswith("/api/progress/"):
            patch_cache_control(response, private=True, max_age=60)
        elif request.path.startswith("/api/leaderboard/"):
            patch_cache_control(response, public=True, max_age=120)

        return response


class RateLimitMiddleware(MiddlewareMixin):
    """Rate limiting middleware with Redis."""

    def __init__(self, get_response):
        super().__init__(get_response)
        self.limiter = RateLimiter()

    def process_request(self, request):
        # Skip for admin, static, health
        skip_paths = ["/admin/", "/static/", "/health/", "/media/"]
        if any(request.path.startswith(path) for path in skip_paths):
            return None

        # Get client identifier
        ip = request.META.get("REMOTE_ADDR")
        if hasattr(request, "user") and request.user.is_authenticated:
            key = f"{ip}:{request.user.id}"
        else:
            key = ip

        # Check rate limit
        if not self.limiter.is_allowed(key):
            remaining = self.limiter.get_remaining(key)
            return JsonResponse(
                {
                    "error": "Rate limit exceeded",
                    "message": "Too many requests. Please try again later.",
                    "remaining": remaining,
                },
                status=429,
            )

        # Store key on request for process_response
        request._rate_limit_key = key
        return None

    def process_response(self, request, response):
        if hasattr(request, "_rate_limit_key"):
            try:
                response["X-RateLimit-Remaining"] = str(
                    self.limiter.get_remaining(request._rate_limit_key)
                )
            except Exception:
                pass
        return response
