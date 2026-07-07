"""
Middleware for cache control headers.
"""

from django.utils.deprecation import MiddlewareMixin
from django.utils.cache import patch_cache_control, get_max_age
import logging

logger = logging.getLogger(__name__)


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
