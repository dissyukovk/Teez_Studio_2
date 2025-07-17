# ftback/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async # Helper for async consumer to call sync code

# Your existing TaskProgressConsumer can remain if needed for other user-specific progress
class TaskProgressConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user_id = self.scope['url_route']['kwargs']['user_id']
        self.group_name = f'user_task_{self.user_id}'

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()
        print(f"WebSocket connected for user {self.user_id} to group {self.group_name}")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
        print(f"WebSocket disconnected for user {self.user_id}")

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']
        print(f"Received message from frontend for user {self.user_id}: {message}")

    async def send_task_progress(self, event):
        message = event['message']
        await self.send(text_data=json.dumps(message))


