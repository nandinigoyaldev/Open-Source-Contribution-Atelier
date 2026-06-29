import json

from channels.generic.websocket import AsyncWebsocketConsumer


class LeaderboardConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = "leaderboard_updates"

        # Join the leaderboard updates group
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        # Leave the leaderboard updates group
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # Receive message from group
    async def leaderboard_update(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps(event))
