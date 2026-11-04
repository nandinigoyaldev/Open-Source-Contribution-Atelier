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
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import UntypedToken

from config.db_router import _local, mark_user_dirty

logger = logging.getLogger(__name__)

WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def resolve_user_id(request):
    """
    The id of the user making the request, or None.

    API clients authenticate with a JWT, and DRF only checks it inside the view, so by the time
    this middleware runs ``request.user`` is anonymous for them. Without reading the token
    ``mark_user_dirty`` and the router's read-after-write check would never see an API user, and
    their reads right after a write could come from a lagging replica. The signature and expiry
    are verified (no database lookup); the id is only used to pick a database, not to authorize.
    """
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        return user.pk

    header = request.META.get("HTTP_AUTHORIZATION", "")
    scheme, _, raw = header.partition(" ")
    if scheme.lower() != "bearer" or not raw.strip():
        return None
    try:
        claim = UntypedToken(raw.strip()).get(str(api_settings.USER_ID_CLAIM))
    except TokenError:
        return None
    except Exception:  # a malformed token must never break the request
        logger.debug("ReadAfterWrite: could not read the token", exc_info=True)
        return None
    try:
        return int(claim)
    except (TypeError, ValueError):
        return None


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
        user_id = resolve_user_id(request)
        _local.user_id = user_id

        try:
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
            return response
        finally:
            # Clean up thread-local to prevent bleed between requests
            _local.user_id = None
