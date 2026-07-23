"""
WebSocket consumer for the platform activity feed.

@file consumers.py
@location backend/apps/feed/consumers.py
"""

import asyncio
import json
import logging
import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)

# Close early enough before hard token expiry that the client has time to
# refresh its access token and reconnect before it's dropped mid-session.
TOKEN_EXPIRY_GRACE_SECONDS = 10
CLOSE_CODE_UNAUTHENTICATED = 4001
CLOSE_CODE_TOKEN_EXPIRED = 4003


class FeedConsumer(AsyncWebsocketConsumer):
    """
    Every connection must be authenticated (JWT, via JWTAuthMiddleware —
    see config/asgi.py). Once connected, the client is placed into:

      - a personal group  ``feed_user_<id>``      -> events targeted at them
      - an org-scoped group ``feed_org_<org_id>``  -> only if the user
        belongs to an organization, for org-wide feed events

    Clients no longer receive the entire platform's feed; only events
    broadcast to a group they're actually a member of.
    """

    async def connect(self):
        user = self.scope.get("user")

        if not user or not user.is_authenticated:
            logger.warning("Feed WS rejected: unauthenticated connection attempt")
            await self.close(code=CLOSE_CODE_UNAUTHENTICATED)
            return

        self.user_id = str(user.id)
        self.personal_group = f"feed_user_{self.user_id}"
        self.org_group = None
        self._expiry_task = None

        await self.channel_layer.group_add(self.personal_group, self.channel_name)

        org_id = await self.get_organization_id(user)
        if org_id is not None:
            self.org_group = f"feed_org_{org_id}"
            await self.channel_layer.group_add(self.org_group, self.channel_name)

        await self.accept()
        logger.info(
            "Feed WS connected: user=%s personal_group=%s org_group=%s",
            self.user_id,
            self.personal_group,
            self.org_group,
        )

        # Handle auth token expiry gracefully: schedule a proactive close
        # shortly before the JWT expires so the client can refresh its
        # token and reconnect, instead of being dropped without warning
        # (or, worse, staying "connected" on a channel layer group after
        # its auth has technically lapsed).
        expires_at = self.scope.get("token_expires_at")
        if expires_at:
            self._expiry_task = asyncio.ensure_future(
                self._close_on_token_expiry(expires_at)
            )

    async def disconnect(self, close_code):
        if getattr(self, "_expiry_task", None):
            self._expiry_task.cancel()
        if hasattr(self, "personal_group"):
            await self.channel_layer.group_discard(
                self.personal_group, self.channel_name
            )
        if getattr(self, "org_group", None):
            await self.channel_layer.group_discard(self.org_group, self.channel_name)
        logger.info(
            "Feed WS disconnected: user=%s code=%s",
            getattr(self, "user_id", "anonymous"),
            close_code,
        )

    async def receive(self, text_data=None, bytes_data=None):
        # The feed is a read-only broadcast channel today; the only inbound
        # message we support is a keep-alive ping from the client.
        try:
            data = json.loads(text_data or "{}")
        except json.JSONDecodeError:
            return
        if data.get("action") == "ping":
            await self.send(text_data=json.dumps({"type": "pong"}))

    # ------------------------------------------------------------------ #
    # Channel-layer event handlers (called by group_send)                #
    # ------------------------------------------------------------------ #
    async def feed_event(self, event):
        """Relay a feed event pushed via group_send to this client."""
        await self.send(text_data=json.dumps(event["data"]))

    # ------------------------------------------------------------------ #
    # Helpers                                                             #
    # ------------------------------------------------------------------ #
    @database_sync_to_async
    def get_organization_id(self, user):
        profile = getattr(user, "user_profile", None)
        if profile and profile.organization_id:
            return profile.organization_id
        return None

    async def _close_on_token_expiry(self, expires_at):
        delay = max(0, expires_at - time.time() - TOKEN_EXPIRY_GRACE_SECONDS)
        try:
            await asyncio.sleep(delay)
            logger.info(
                "Feed WS closing due to token expiry: user=%s",
                getattr(self, "user_id", "anonymous"),
            )
            await self.close(code=CLOSE_CODE_TOKEN_EXPIRED)
        except asyncio.CancelledError:
            # Client disconnected normally before expiry — nothing to do.
            pass
