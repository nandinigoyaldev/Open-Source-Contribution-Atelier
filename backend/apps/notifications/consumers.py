import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from .models import Notification

from apps.core.channel_safety import safe_group_add, safe_group_discard

logger = logging.getLogger(__name__)


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer that each authenticated user connects to.
    Group name  →  notifications_<user_id>
    """

    async def connect(self):
        user = self.scope.get("user")

        # Reject anonymous connections
        if not user or not user.is_authenticated:
            logger.warning("WS rejected: unauthenticated user")
            await self.close(code=4001)
            return

        self.user_id = str(user.id)
        self.group_name = f"notifications_{self.user_id}"
        self.realtime_degraded = False

        # Join personal channel group — degrade if Redis/channel layer is down
        joined = await safe_group_add(self.group_name, self.channel_name)
        if not joined:
            self.realtime_degraded = True
            logger.warning(
                "WS connected in degraded mode (no channel group): user=%s",
                self.user_id,
            )

        await self.accept()
        logger.info("WS connected: user=%s group=%s", self.user_id, self.group_name)

        # Send unread count on connect
        unread = await self.get_unread_count(user)
        payload = {
            "type": "connection_established",
            "unread_count": unread,
        }
        if self.realtime_degraded:
            payload["degraded"] = True
            payload["detail"] = (
                "Realtime channel layer unavailable; inbox will poll over HTTP."
            )
        await self.send(text_data=json.dumps(payload))

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await safe_group_discard(self.group_name, self.channel_name)
            logger.info(
                "WS disconnected: group=%s code=%s", self.group_name, close_code
            )

    # Messages received FROM the browser (e.g. mark-as-read)
    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data or "{}")
            action = data.get("action")

            if action == "mark_read":
                notif_id = data.get("notification_id")
                if notif_id:
                    await self.mark_notification_read(notif_id)
                    await self.send(
                        text_data=json.dumps(
                            {
                                "type": "marked_read",
                                "notification_id": notif_id,
                            }
                        )
                    )
        except json.JSONDecodeError:
            logger.error("WS receive: invalid JSON")

    # ------------------------------------------------------------------ #
    # Channel-layer event handlers  (called by group_send)               #
    # ------------------------------------------------------------------ #
    async def send_notification(self, event):
        """Relay a notification pushed by a signal / task."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "notification",
                    "notification": event["notification"],
                }
            )
        )

    # ------------------------------------------------------------------ #
    # DB helpers (run in thread pool)                                     #
    # ------------------------------------------------------------------ #
    @database_sync_to_async
    def get_unread_count(self, user):
        from .models import Notification

        return Notification.objects.filter(recipient=user, is_read=False).count()

    @database_sync_to_async
    def mark_notification_read(self, notif_id):
        from .models import Notification

        Notification.objects.filter(id=notif_id, recipient=self.scope["user"]).update(
            is_read=True
        )


class LeaderboardConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for live leaderboard updates.
    Group name  →  leaderboard
    """

    async def connect(self):
        user = self.scope.get("user")

        # Reject anonymous connections
        if not user or not user.is_authenticated:
            logger.warning("WS Leaderboard rejected: unauthenticated user")
            await self.close(code=4001)
            return

        self.group_name = "leaderboard"

        joined = await safe_group_add(self.group_name, self.channel_name)
        await self.accept()
        if not joined:
            logger.warning(
                "WS Leaderboard degraded (no channel group): user=%s", user.id
            )
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "connection_established",
                        "degraded": True,
                        "detail": (
                            "Realtime leaderboard unavailable; "
                            "Redis/channel layer down."
                        ),
                    }
                )
            )
        else:
            logger.info(
                "WS Leaderboard connected: user=%s group=%s", user.id, self.group_name
            )

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await safe_group_discard(self.group_name, self.channel_name)
            logger.info(
                "WS Leaderboard disconnected: group=%s code=%s",
                self.group_name,
                close_code,
            )

    async def leaderboard_update(self, event):
        """Relay leaderboard update event to the websocket client."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "leaderboard_update",
                    "event": event.get("event", "xp_update"),
                    "user_id": event.get("user_id"),
                    "username": event.get("username"),
                    "xp": event.get("xp"),
                    "message": event.get("message", "Leaderboard update triggered"),
                }
            )
        )
