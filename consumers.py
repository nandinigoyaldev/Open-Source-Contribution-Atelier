import json
from channels.generic.websocket import AsyncWebsocketConsumer
from .models import Suggestion

class ReviewConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.room_name = f'review_{self.session_id}'
        
        await self.channel_layer.group_add(self.room_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        event_type = data.get('type')
        
        if event_type == 'suggestion_updated':
            await self.channel_layer.group_send(
                self.room_name,
                {
                    'type': 'suggestion_update',
                    'data': data['data']
                }
            )

    async def suggestion_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'suggestion_update',
            'data': event['data']
        }))