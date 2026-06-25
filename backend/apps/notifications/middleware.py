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


class JWTAuthMiddleware:
    """ASGI middleware: attaches an authenticated user to the scope."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("websocket", "http"):
            qs = parse_qs(scope.get("query_string", b"").decode())
            token = qs.get("token", [None])[0]
            scope["user"] = (
                await get_user_from_token(token) if token else AnonymousUser()
            )
        return await self.inner(scope, receive, send)
