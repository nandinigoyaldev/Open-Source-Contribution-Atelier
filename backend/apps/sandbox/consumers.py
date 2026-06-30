import json

from channels.generic.websocket import AsyncWebsocketConsumer


class SandboxConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_group_name = "sandbox_group"
        self.debug_process = None
        self.debug_file = None
        self.debug_task = None

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        await self._cleanup_debug_session()

    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            action = text_data_json.get("action")

            if action == "code_update":
                code = text_data_json.get("code")
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "code_message",
                        "code": code,
                        "sender_channel_name": self.channel_name,
                    },
                )
            elif action == "execute_code":
                code = text_data_json.get("code")
                from .services import stream_python_execution

                user_id = "anonymous"
                if self.scope.get("user") and getattr(self.scope["user"], "is_authenticated", False):
                    user_id = str(self.scope["user"].id)
                else:
                    user_id = self.channel_name

                async def send_callback(message_data):
                    await self.send(text_data=json.dumps(message_data))

                await stream_python_execution(code, send_callback, user_id=user_id)
            
            elif action == "debug_start":
                code = text_data_json.get("code")
                breakpoints = text_data_json.get("breakpoints", [])
                from .services import start_debug_session
                import os
                import asyncio
                
                await self._cleanup_debug_session()
                
                async def send_callback(message_data):
                    await self.send(text_data=json.dumps(message_data))
                    
                self.debug_process, self.debug_file = await start_debug_session(code, breakpoints)
                
                async def read_debug_output():
                    try:
                        while True:
                            line = await self.debug_process.stdout.readline()
                            if not line:
                                break
                            
                            try:
                                data = json.loads(line.decode("utf-8"))
                                await send_callback(data)
                            except json.JSONDecodeError:
                                # Normal print statements from user code
                                await send_callback({"type": "execution_output", "output": line.decode("utf-8")})
                    except Exception:
                        pass
                    finally:
                        await self._cleanup_debug_session()
                
                self.debug_task = asyncio.create_task(read_debug_output())
                
            elif action in ["debug_step", "debug_next", "debug_continue"]:
                if self.debug_process and self.debug_process.stdin:
                    cmd = action.split("_")[1] # step, next, continue
                    self.debug_process.stdin.write(f"{cmd}\n".encode("utf-8"))
                    await self.debug_process.stdin.drain()
                    
            elif action == "debug_stop":
                await self._cleanup_debug_session()
                
            elif action == "debug_breakpoint_add":
                if self.debug_process and self.debug_process.stdin:
                    line = text_data_json.get("line")
                    self.debug_process.stdin.write(f"break {line}\n".encode("utf-8"))
                    await self.debug_process.stdin.drain()
                    
            elif action == "debug_breakpoint_remove":
                if self.debug_process and self.debug_process.stdin:
                    line = text_data_json.get("line")
                    self.debug_process.stdin.write(f"clear {line}\n".encode("utf-8"))
                    await self.debug_process.stdin.drain()
        except Exception:
            pass

    async def _cleanup_debug_session(self):
        import os
        if self.debug_process:
            try:
                self.debug_process.kill()
            except ProcessLookupError:
                pass
            self.debug_process = None
            
        if self.debug_task:
            self.debug_task.cancel()
            self.debug_task = None
            
        if self.debug_file and os.path.exists(self.debug_file):
            try:
                os.remove(self.debug_file)
            except Exception:
                pass
            self.debug_file = None

    async def code_message(self, event):
        code = event["code"]
        sender_channel_name = event.get("sender_channel_name")

        if self.channel_name != sender_channel_name:
            await self.send(
                text_data=json.dumps({"action": "code_update", "code": code})
            )


class CollabConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope["url_route"]["kwargs"]["room_id"]
        self.room_group_name = f"collab_{self.room_id}"

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if bytes_data:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "collab_message",
                    "bytes_data": bytes_data,
                    "sender_channel_name": self.channel_name,
                },
            )

    async def collab_message(self, event):
        bytes_data = event.get("bytes_data")
        sender_channel_name = event.get("sender_channel_name")

        if self.channel_name != sender_channel_name:
            await self.send(bytes_data=bytes_data)
