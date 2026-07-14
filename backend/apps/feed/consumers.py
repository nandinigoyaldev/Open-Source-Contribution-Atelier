import json
from channels.generic.websocket import AsyncWebsocketConsumer
from .models import FeedEvent

class FeedConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add("feed", self.channel_name)
        await self.accept()
    
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("feed", self.channel_name)
    
    async def feed_event(self, event):
        await self.send(text_data=json.dumps(event['data']))