import asyncio
import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.cache import cache

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

        if room_id.startswith("dm_"):
            parts = room_id.split("_")
            if len(parts) == 3:
                try:
                    u1, u2 = int(parts[1]), int(parts[2])
                    if self.user.id not in [u1, u2]:
                        logger.warning("WS Chat rejected: unauthorized DM access")
                        await self.close(code=4003)
                        return
                except ValueError:
                    await self.close(code=4002)
                    return

        self.user = user
        self.room_id = room_id
        self.group_name = f"chat_{room_id}"
        self.typing_timeout_task = None

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
                        "id": msg["id"],
                        "parent_id": msg["parent_id"],
                        "username": msg["username"],
                        "user_id": msg["user_id"],
                        "message": msg["content"],
                        "created_at": msg["created_at"],
                    }
                )
            )

        # Presence synchronization
        is_new = await self.add_user_to_presence()
        online_users = await self.get_online_users()

        await self.send(
            text_data=json.dumps(
                {
                    "type": "presence_sync",
                    "users": online_users,
                }
            )
        )

        if is_new:
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "presence_joined",
                    "username": self.user.username,
                    "user_id": self.user.id,
                },
            )

    @database_sync_to_async
    def get_last_50_messages(self):
        qs = Message.objects.filter(room_id=self.room_id).order_by("-created_at")[:50]
        return [
            {
                "id": m.id,
                "parent_id": m.parent_id,
                "username": m.user.username,
                "user_id": m.user.id,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
            }
            for m in reversed(qs)
        ]

    @database_sync_to_async
    def save_message(self, user, room_id, content, parent_id=None):
        return Message.objects.create(
            user=user, room_id=room_id, content=content, parent_id=parent_id
        )

    async def disconnect(self, close_code):
        if getattr(self, "typing_timeout_task", None):
            self.typing_timeout_task.cancel()

        is_gone = await self.remove_user_from_presence()
        if hasattr(self, "group_name"):
            if is_gone:
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        "type": "presence_left",
                        "username": self.user.username,
                        "user_id": self.user.id,
                    },
                )
            # Automatically clear typing state on disconnect
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
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            logger.info(
                "WS Chat disconnected: group=%s code=%s",
                self.group_name,
                close_code,
            )

    @database_sync_to_async
    def add_user_to_presence(self):
        key = f"chat_presence_{self.room_id}"
        users = cache.get(key, {})
        uid_str = str(self.user.id)
        is_new = False
        if uid_str not in users:
            users[uid_str] = {"username": self.user.username, "count": 1}
            is_new = True
        else:
            users[uid_str]["count"] += 1
        cache.set(key, users, timeout=86400)
        return is_new

    @database_sync_to_async
    def remove_user_from_presence(self):
        key = f"chat_presence_{self.room_id}"
        users = cache.get(key, {})
        uid_str = str(self.user.id)
        is_gone = False
        if uid_str in users:
            users[uid_str]["count"] -= 1
            if users[uid_str]["count"] <= 0:
                del users[uid_str]
                is_gone = True
        cache.set(key, users, timeout=86400)
        return is_gone

    @database_sync_to_async
    def get_online_users(self):
        key = f"chat_presence_{self.room_id}"
        users = cache.get(key, {})
        return [
            {"user_id": int(uid), "username": info["username"]}
            for uid, info in users.items()
        ]

    async def clear_typing_state(self):
        try:
            await asyncio.sleep(4)  # Short timeout to clear typing state
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
        except asyncio.CancelledError:
            pass

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data or "{}")
        except json.JSONDecodeError:
            logger.error("WS Chat receive: invalid JSON")
            return

        action = data.get("action")

        if action == "typing_start":
            if getattr(self, "typing_timeout_task", None):
                self.typing_timeout_task.cancel()
            self.typing_timeout_task = asyncio.create_task(self.clear_typing_state())

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
            if getattr(self, "typing_timeout_task", None):
                self.typing_timeout_task.cancel()
                self.typing_timeout_task = None

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

        elif action == "public_key":
            public_key = data.get("public_key")
            if public_key:
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        "type": "public_key_broadcast",
                        "username": self.user.username,
                        "user_id": self.user.id,
                        "public_key": public_key,
                        "sender_channel": self.channel_name,
                    },
                )

        elif action == "send_message":
            content = data.get("message", "")
            parent_id = data.get("parent_id")
            if content:
                is_allowed = await self.check_rate_limit(
                    f"throttle_chat_ws_{self.user.id}", 30, 60
                )
                if not is_allowed:
                    await self.send(
                        text_data=json.dumps(
                            {
                                "type": "error",
                                "message": "Rate limit exceeded. Please wait before sending more messages.",
                            }
                        )
                    )
                    return

                msg = await self.save_message(
                    self.user, self.room_id, content, parent_id
                )
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        "type": "chat_message",
                        "id": msg.id,
                        "parent_id": msg.parent_id,
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
                    "id": event.get("id"),
                    "parent_id": event.get("parent_id"),
                    "username": event["username"],
                    "user_id": event["user_id"],
                    "message": event["message"],
                    "created_at": event.get("created_at"),
                }
            )
        )

    async def presence_joined(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "presence_joined",
                    "username": event["username"],
                    "user_id": event["user_id"],
                }
            )
        )

    async def presence_left(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "presence_left",
                    "username": event["username"],
                    "user_id": event["user_id"],
                }
            )
        )
