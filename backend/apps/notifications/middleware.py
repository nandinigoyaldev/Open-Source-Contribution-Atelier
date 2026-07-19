"""
JWT Token Authentication middleware for Django Channels.
Reads the token from the query string:  ws://host/ws/notifications/?token=<JWT>
"""

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser


@database_sync_to_async
def get_user_from_token(token_key):
    try:
        from django.contrib.auth import get_user_model
        from rest_framework_simplejwt.tokens import AccessToken

        User = get_user_model()
        token = AccessToken(token_key)
        return User.objects.get(id=token["user_id"])
    except Exception:
        return AnonymousUser()


def get_token_expiry(token_key):
    """
    Returns the token's expiry as a POSIX timestamp (float), or None if the
    token is missing/invalid. Kept synchronous + side-effect free so it's
    cheap to call from the async middleware without a thread hop.
    """
    if not token_key:
        return None
    try:
        from rest_framework_simplejwt.tokens import AccessToken

        token = AccessToken(token_key)
        return float(token["exp"])
    except Exception:
        return None


class JWTAuthMiddleware:
    """ASGI middleware: attaches an authenticated user to the scope."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        # BUGFIX: Create a shallow copy of scope to prevent ASGI cross-request pollution
        scope = dict(scope)

        if scope["type"] in ("websocket", "http"):
            qs = parse_qs(scope.get("query_string", b"").decode())
            token = qs.get("token", [None])[0]
            scope["user"] = (
                await get_user_from_token(token) if token else AnonymousUser()
            )
            # Attaches when the current token expires (POSIX timestamp) so
            # long-lived WebSocket consumers (e.g. FeedConsumer) can close
            # gracefully near expiry instead of the client silently losing
            # events after the token dies.
            scope["token_expires_at"] = get_token_expiry(token)

        return await self.inner(scope, receive, send)
