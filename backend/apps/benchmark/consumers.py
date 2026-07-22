"""
WebSocket consumer for benchmarking.
"""

import json
from channels.generic.websocket import AsyncWebsocketConsumer


class BenchmarkConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for performance benchmarking.
    """

    async def connect(self):
        """Handle connection."""
        self.client_id = self.scope["url_route"]["kwargs"].get("client_id", "unknown")
        self.group_name = "benchmark_group"

        # Join group for broadcast testing
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send connection acknowledgment
        await self.send(
            json.dumps(
                {
                    "type": "connected",
                    "client_id": self.client_id,
                    "timestamp": time.time(),
                }
            )
        )

    async def disconnect(self, close_code):
        """Handle disconnection."""
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        """Handle received messages."""
        try:
            data = json.loads(text_data)

            if data.get("type") == "benchmark":
                # Echo back for latency measurement
                await self.send(
                    json.dumps(
                        {
                            "type": "benchmark_response",
                            "client_id": self.client_id,
                            "sequence": data.get("sequence"),
                            "timestamp": time.time(),
                        }
                    )
                )

        except json.JSONDecodeError:
            pass

    async def benchmark_message(self, event):
        """Handle broadcast messages."""
        await self.send(
            json.dumps(
                {
                    "type": "broadcast",
                    "data": event.get("data", {}),
                    "timestamp": time.time(),
                }
            )
        )
