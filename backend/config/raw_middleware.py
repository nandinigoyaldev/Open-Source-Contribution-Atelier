"""
ReadAfterWriteMiddleware

Tracks the currently authenticated user in thread-local storage so that
PrimaryReplicaRouter can route their reads to the primary database for a
short window after they have performed a write (read-after-write consistency).

After any mutating request (POST / PUT / PATCH / DELETE) for an authenticated
user, the user's ID is written to the cache with a short TTL via
`mark_user_dirty()`.  Subsequent GET requests within that window are then
transparently served from the primary rather than a stale replica.
"""
import logging
import threading

from django.conf import settings

from config.db_router import _local, mark_user_dirty

logger = logging.getLogger(__name__)

WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class ReadAfterWriteMiddleware:
    """
    Django middleware for per-user read-after-write consistency.

    Add this to MIDDLEWARE *before* AuthenticationMiddleware so that
    request.user is available:

        MIDDLEWARE = [
            ...
            "config.raw_middleware.ReadAfterWriteMiddleware",
            ...
        ]
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Expose user_id on the thread-local so the router can see it
        user = getattr(request, "user", None)
        user_id = user.pk if user and user.is_authenticated else None
        _local.user_id = user_id

        response = self.get_response(request)

        # After a mutating request, flag the user as dirty
        if user_id and request.method in WRITE_METHODS:
            mark_user_dirty(user_id)
            logger.debug(
                "ReadAfterWrite: user %s dirtied after %s %s",
                user_id,
                request.method,
                request.path,
            )

        # Clean up thread-local to prevent bleed between requests
        _local.user_id = None
        return response
