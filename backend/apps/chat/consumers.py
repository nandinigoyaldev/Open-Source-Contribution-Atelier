import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .models import Message

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time chat (including typing indicators).

    URL pattern:  ws://host/ws/chat/<room_id>/ ?token=<JWT>
    """

    async def connect(self):
        user = self.scope.get("user")

        if not user or not user.is_authenticated:
            logger.warning("WS Chat rejected: unauthenticated user")
            await self.close(code=4001)
            return

        room_id = self.scope["url_route"]["kwargs"].get("room_id")
        if not room_id:
            logger.warning("WS Chat rejected: missing room_id")
            await self.close(code=4002)
            return

        self.user = user
        self.room_id = room_id
        self.group_name = f"chat_{room_id}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        logger.info("WS Chat connected: user=%s room=%s", self.user.id, self.room_id)

        await self.send(
            text_data=json.dumps(
                {
                    "type": "connection_established",
                    "room_id": self.room_id,
                    "user_id": self.user.id,
                }
            )
        )

        messages = await self.get_last_50_messages()
        for msg in messages:
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "new_message",
                        "username": msg["username"],
                        "user_id": msg["user_id"],
                        "message": msg["content"],
                        "created_at": msg["created_at"],
                    }
                )
            )

    @database_sync_to_async
    def get_last_50_messages(self):
        qs = Message.objects.filter(room_id=self.room_id).order_by("-created_at")[:50]
        return [
            {
                "username": m.user.username,
                "user_id": m.user.id,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
            }
            for m in reversed(qs)
        ]

    @database_sync_to_async
    def save_message(self, user, room_id, content):
        return Message.objects.create(user=user, room_id=room_id, content=content)

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            logger.info(
                "WS Chat disconnected: group=%s code=%s",
                self.group_name,
                close_code,
            )

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data or "{}")
        except json.JSONDecodeError:
            logger.error("WS Chat receive: invalid JSON")
            return

        action = data.get("action")

        if action == "typing_start":
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "user_typing",
                    "action": "typing_start",
                    "username": self.user.username,
                    "user_id": self.user.id,
                    "sender_channel": self.channel_name,
                },
            )

        elif action == "typing_stop":
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "user_typing",
                    "action": "typing_stop",
                    "username": self.user.username,
                    "user_id": self.user.id,
                    "sender_channel": self.channel_name,
                },
            )

        elif action == "send_message":
            content = data.get("message", "")
            if content:
                msg = await self.save_message(self.user, self.room_id, content)
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        "type": "chat_message",
                        "username": self.user.username,
                        "user_id": self.user.id,
                        "message": content,
                        "created_at": msg.created_at.isoformat(),
                        "sender_channel": self.channel_name,
                    },
                )

    async def user_typing(self, event):
        if event["sender_channel"] == self.channel_name:
            return
        await self.send(
            text_data=json.dumps(
                {
                    "type": "typing",
                    "action": event["action"],
                    "username": event["username"],
                    "user_id": event["user_id"],
                }
            )
        )

    async def public_key_broadcast(self, event):
        if event["sender_channel"] == self.channel_name:
            return
        await self.send(
            text_data=json.dumps(
                {
                    "type": "public_key",
                    "username": event["username"],
                    "user_id": event["user_id"],
                    "public_key": event["public_key"],
                }
            )
        )

    async def chat_message(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "new_message",
                    "username": event["username"],
                    "user_id": event["user_id"],
                    "message": event["message"],
                    "created_at": event.get("created_at"),
                }
            )
        )
