import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class WebRTCSignalingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            logger.warning("WS WebRTC rejected: unauthenticated user")
            await self.close(code=4001)
            return

        self.room_id = self.scope["url_route"]["kwargs"].get("room_id")
        if not self.room_id:
            logger.warning("WS WebRTC rejected: missing room_id")
            await self.close(code=4002)
            return

        self.user = user
        self.group_name = f"webrtc_{self.room_id}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        logger.info("WS WebRTC connected: user=%s room=%s", self.user.id, self.room_id)

        # Notify others in the room
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "peer_joined",
                "user_id": self.user.id,
                "username": self.user.username,
                "sender_channel": self.channel_name,
            },
        )

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            # Notify others
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "peer_left",
                    "user_id": self.user.id,
                    "username": self.user.username,
                    "sender_channel": self.channel_name,
                },
            )
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            logger.info(
                "WS WebRTC disconnected: group=%s code=%s", self.group_name, close_code
            )

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data or "{}")
        except json.JSONDecodeError:
            logger.error("WS WebRTC receive: invalid JSON")
            return

        action = data.get("action")

        if action in ["offer", "answer", "ice-candidate"]:
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "webrtc_signal",
                    "action": action,
                    "data": data.get("data"),
                    "user_id": self.user.id,
                    "sender_channel": self.channel_name,
                },
            )

    async def peer_joined(self, event):
        if event["sender_channel"] == self.channel_name:
            return
        await self.send(
            text_data=json.dumps(
                {
                    "type": "peer_joined",
                    "user_id": event["user_id"],
                    "username": event["username"],
                }
            )
        )

    async def peer_left(self, event):
        if event["sender_channel"] == self.channel_name:
            return
        await self.send(
            text_data=json.dumps(
                {
                    "type": "peer_left",
                    "user_id": event["user_id"],
                    "username": event["username"],
                }
            )
        )

    async def webrtc_signal(self, event):
        if event["sender_channel"] == self.channel_name:
            return
        await self.send(
            text_data=json.dumps(
                {
                    "type": "webrtc_signal",
                    "action": event["action"],
                    "data": event["data"],
                    "user_id": event["user_id"],
                }
            )
        )
