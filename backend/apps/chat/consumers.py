import asyncio
import json
import logging
import time
from typing import Optional

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from django.core.cache import cache

from apps.accounts.throttles import RedisLuaRateLimiter  # type: ignore

from .models import Message

logger = logging.getLogger(__name__)

_IN_MEMORY_RATE_LIMITS: dict[str, list[float]] = {}
_LAST_RATE_LIMIT_WARN_TIME: float = 0.0


def _log_rate_limit_warning(msg: str, exc: Exception) -> None:
    global _LAST_RATE_LIMIT_WARN_TIME
    now = time.time()
    warn_interval = getattr(settings, "CHAT_WS_RATE_LIMIT_LOG_WARN_INTERVAL", 60)
    if now - _LAST_RATE_LIMIT_WARN_TIME >= warn_interval:
        _LAST_RATE_LIMIT_WARN_TIME = now
        logger.warning("%s: %s", msg, exc)


def _in_memory_rate_limit_check(
    key: str, max_requests: int, window_seconds: int
) -> bool:
    try:
        now = time.time()
        history = _IN_MEMORY_RATE_LIMITS.get(key, [])
        history = [t for t in history if now - t < window_seconds]
        if len(history) >= max_requests:
            _IN_MEMORY_RATE_LIMITS[key] = history
            return False
        history.append(now)
        _IN_MEMORY_RATE_LIMITS[key] = history
        return True
    except Exception as e:
        _log_rate_limit_warning("In-memory rate limiter fallback error", e)
        return False


class ChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time chat (including typing indicators).

    URL pattern:  ws://host/ws/chat/<room_id>/ ?token=<JWT>
    """

    async def check_rate_limit(
        self,
        key: str,
        max_requests: Optional[int] = None,
        window_seconds: Optional[int] = None,
    ) -> bool:
        if max_requests is None:
            max_requests = getattr(settings, "CHAT_WS_RATE_LIMIT_MAX_REQUESTS", 30)
        if window_seconds is None:
            window_seconds = getattr(settings, "CHAT_WS_RATE_LIMIT_WINDOW_SECONDS", 60)

        backend = getattr(settings, "RATE_LIMIT_BACKEND", "local").lower()

        if backend == "redis":
            try:
                limiter = RedisLuaRateLimiter(
                    key=key,
                    max_requests=max_requests,
                    window_seconds=window_seconds,
                )
                allowed, _, _ = limiter.check()
                return allowed
            except Exception as e:
                _log_rate_limit_warning(
                    "Chat WS Redis Lua throttling failed, falling back to local cache/in-memory",
                    e,
                )

        try:
            current = cache.get(key, 0)
            if current >= max_requests:
                return False
            if current == 0:
                cache.set(key, 1, window_seconds)
            else:
                try:
                    cache.incr(key)
                except ValueError:
                    cache.set(key, current + 1, window_seconds)
            return True
        except Exception as e:
            _log_rate_limit_warning(
                "Chat WS rate limiter cache failed, falling back to in-memory limiter",
                e,
            )
            return _in_memory_rate_limit_check(key, max_requests, window_seconds)

    async def connect(self):
        user = self.scope.get("user")

        if not user or not user.is_authenticated:
            logger.warning("WS Chat rejected: unauthenticated user")
            await self.close(code=4001)
            return

        url_route = self.scope.get("url_route", {})
        kwargs = url_route.get("kwargs", {}) if url_route else {}
        room_id = kwargs.get("room_id")

        if not room_id:
            logger.warning("WS Chat rejected: missing room_id")
            await self.close(code=4002)
            return

        user_id = getattr(user, "pk", getattr(user, "id", None))

        if room_id.startswith("dm_"):
            parts = room_id.split("_")
            if len(parts) == 3:
                try:
                    u1, u2 = int(parts[1]), int(parts[2])

                    if user_id not in [u1, u2]:

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

        logger.info("WS Chat connected: user=%s room=%s", user_id, self.room_id)

        await self.send(
            text_data=json.dumps(
                {
                    "type": "connection_established",
                    "room_id": self.room_id,
                    "user_id": user_id,
                }
            )
        )

        query_string = self.scope.get("query_string", b"").decode("utf-8")
        since_id = None
        if query_string:
            from urllib.parse import parse_qs

            params = parse_qs(query_string)
            since_id_param = params.get(
                "since_id", params.get("last_message_id", [None])
            )[0]
            if since_id_param:
                try:
                    since_id = int(since_id_param)
                except (ValueError, TypeError):
                    since_id = None

        if since_id is not None and since_id > 0:
            gap = await self.check_retention_gap(since_id)
            messages = await self.get_messages_since(since_id)
            latest_msg = (
                await Message.objects.filter(room_id=self.room_id)
                .order_by("-id")
                .afirst()
            )
            latest_id = latest_msg.id if latest_msg else since_id
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "history_sync",
                        "room_id": self.room_id,
                        "since_id": since_id,
                        "latest_id": latest_id,
                        "resync_required": gap,
                        "messages": messages,
                    }
                )
            )
        else:
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
                    "username": getattr(self.user, "username", ""),
                    "user_id": user_id,
                    "username": self.user.username,
                    "user_id": self.user.id,
                },
            )

    async def get_last_50_messages(self):
        qs = (
            Message.objects.select_related("user")
            .filter(room_id=self.room_id)
            .order_by("-created_at")[:50]
        )
        messages = [m async for m in qs]
        return [
            {
                "id": m.id,  # type: ignore
                "parent_id": m.parent_id,
                "username": m.user.username,
                "user_id": m.user.id,  # type: ignore
                "content": m.content,
                "created_at": m.created_at.isoformat(),
            }
            for m in reversed(messages)
        ]

    async def get_messages_since(self, since_id: int, limit: int = 100):
        """Fetch messages in room created after `since_id` in ascending ID order."""
        qs = (
            Message.objects.select_related("user")
            .filter(room_id=self.room_id, id__gt=since_id)
            .order_by("id")[:limit]
        )
        messages = [m async for m in qs]
        return [
            {
                "id": m.id,  # type: ignore
                "parent_id": m.parent_id,
                "username": m.user.username,
                "user_id": m.user.id,  # type: ignore
                "content": m.content,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ]

    async def check_retention_gap(self, since_id: int) -> bool:
        """Check if since_id is older than the oldest message in the room (indicating a purge or retention gap)."""
        oldest = (
            await Message.objects.filter(room_id=self.room_id)
            .order_by("id")
            .afirst()
        )
        if oldest and since_id < oldest.id:
            return True
        return False

    async def save_message(self, user, room_id, content, parent_id=None):
        return await Message.objects.acreate(
            user=user, room_id=room_id, content=content, parent_id=parent_id
        )

    async def disconnect(self, code):
        if getattr(self, "typing_timeout_task", None):
            task = self.typing_timeout_task
            if task:
                task.cancel()

        is_gone = await self.remove_user_from_presence()
        user_id = getattr(self.user, "pk", getattr(self.user, "id", None))
        username = getattr(self.user, "username", "")

        if hasattr(self, "group_name"):
            if is_gone:
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        "type": "presence_left",
                        "username": username,
                        "user_id": user_id,
                    },
                )
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "user_typing",
                    "action": "typing_stop",
                    "username": username,
                    "user_id": user_id,
                    "sender_channel": self.channel_name,
                },
            )
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            logger.info(
                "WS Chat disconnected: group=%s code=%s",
                self.group_name,
                code,
            )

    async def add_user_to_presence(self):
        key = f"chat_presence_{self.room_id}"
        users = await cache.aget(key, {})
        user_id = getattr(self.user, "pk", getattr(self.user, "id", None))
        uid_str = str(user_id)
        is_new = False
        if uid_str not in users:
            users[uid_str] = {
                "username": getattr(self.user, "username", ""),
                "count": 1,
            }
            is_new = True
        else:
            users[uid_str]["count"] += 1
        await cache.aset(key, users, timeout=86400)
        return is_new

    async def remove_user_from_presence(self):
        key = f"chat_presence_{self.room_id}"
        users = await cache.aget(key, {})
        user_id = getattr(self.user, "pk", getattr(self.user, "id", None))
        uid_str = str(user_id)
        is_gone = False
        if uid_str in users:
            users[uid_str]["count"] -= 1
            if users[uid_str]["count"] <= 0:
                del users[uid_str]
                is_gone = True
        await cache.aset(key, users, timeout=86400)
        return is_gone

    async def get_online_users(self):
        key = f"chat_presence_{self.room_id}"
        users = await cache.aget(key, {})
        return [
            {"user_id": int(uid), "username": info["username"]}
            for uid, info in users.items()
        ]

    async def clear_typing_state(self):
        try:
            await asyncio.sleep(4)
            user_id = getattr(self.user, "pk", getattr(self.user, "id", None))
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "user_typing",
                    "action": "typing_stop",
                    "username": getattr(self.user, "username", ""),
                    "user_id": user_id,
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
        user_id = getattr(self.user, "pk", getattr(self.user, "id", None))
        username = getattr(self.user, "username", "")

        if action == "typing_start":
            if getattr(self, "typing_timeout_task", None):
                task = self.typing_timeout_task
                if task:
                    task.cancel()
            self.typing_timeout_task = asyncio.create_task(self.clear_typing_state())

            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "user_typing",
                    "action": "typing_start",
                    "username": username,
                    "user_id": user_id,
                    "sender_channel": self.channel_name,
                },
            )

        elif action == "typing_stop":
            if getattr(self, "typing_timeout_task", None):
                task = self.typing_timeout_task
                if task:
                    task.cancel()
                self.typing_timeout_task = None

            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "user_typing",
                    "action": "typing_stop",
                    "username": username,
                    "user_id": user_id,
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
                        "username": username,
                        "user_id": user_id,
                        "public_key": public_key,
                        "sender_channel": self.channel_name,
                    },
                )

        elif action == "ping":
            await self.send(text_data=json.dumps({"type": "pong"}))

        elif action in ["sync_history", "history_sync"]:
            since_id = data.get("since_id") or data.get("last_message_id") or 0
            try:
                since_id = int(since_id)
            except (ValueError, TypeError):
                since_id = 0

            gap = False
            if since_id > 0:
                gap = await self.check_retention_gap(since_id)

            messages = await self.get_messages_since(since_id, limit=100)
            latest_msg = (
                await Message.objects.filter(room_id=self.room_id)
                .order_by("-id")
                .afirst()
            )
            latest_id = latest_msg.id if latest_msg else since_id

            await self.send(
                text_data=json.dumps(
                    {
                        "type": "history_sync",
                        "room_id": self.room_id,
                        "since_id": since_id,
                        "latest_id": latest_id,
                        "resync_required": gap,
                        "messages": messages,
                    }
                )
            )

        elif action == "send_message":
            content = data.get("message", "")
            parent_id = data.get("parent_id")
            if content:
                is_allowed = await self.check_rate_limit(
                    f"throttle_chat_ws_{self.user.id}"
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
                        "id": msg.id,  # type: ignore
                        "parent_id": msg.parent,
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
