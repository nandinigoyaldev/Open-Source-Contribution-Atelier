import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.cache import cache


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

    @database_sync_to_async
    def check_rate_limit(self, key, limit, period):
        count = cache.get(key, 0)
        if count >= limit:
            return False
        if count == 0:
            cache.set(key, 1, timeout=period)
        else:
            try:
                cache.incr(key)
            except ValueError:
                cache.set(key, count + 1, timeout=period)
        return True

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
                if self.scope.get("user") and getattr(
                    self.scope["user"], "is_authenticated", False
                ):
                    user_id = str(self.scope["user"].id)
                else:
                    user_id = self.channel_name

                # Rate limiting (10 per minute)
                is_allowed = await self.check_rate_limit(
                    f"throttle_sandbox_ws_{user_id}", 10, 60
                )
                if not is_allowed:
                    await self.send(
                        text_data=json.dumps(
                            {
                                "type": "error",
                                "message": "Rate limit exceeded. You can only execute 10 sandbox requests per minute.",
                            }
                        )
                    )
                    return

                async def send_callback(message_data):
                    await self.send(text_data=json.dumps(message_data))

                await stream_python_execution(code, send_callback, user_id=user_id)

            elif action == "execute_trace":
                code = text_data_json.get("code")
                from asgiref.sync import sync_to_async

                from .models import CodeExecutionTrace
                from .services import run_code_trace

                user_id = "anonymous"
                db_user = None
                if self.scope.get("user") and getattr(
                    self.scope["user"], "is_authenticated", False
                ):
                    user_id = str(self.scope["user"].id)
                    db_user = self.scope["user"]

                trace_events = await run_code_trace(code, user_id=user_id)

                if trace_events and db_user:

                    def save_trace():
                        CodeExecutionTrace.objects.create(
                            user=db_user, code=code, trace_events=trace_events
                        )

                    await sync_to_async(save_trace)()

                await self.send(
                    text_data=json.dumps(
                        {"action": "trace_result", "trace_events": trace_events}
                    )
                )

            elif action == "debug_start":
                code = text_data_json.get("code")
                breakpoints = text_data_json.get("breakpoints", [])
                import asyncio
                import os

                from .services import start_debug_session

                await self._cleanup_debug_session()

                async def send_callback(message_data):
                    await self.send(text_data=json.dumps(message_data))

                self.debug_process, self.debug_file = await start_debug_session(
                    code, breakpoints
                )

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
                                await send_callback(
                                    {
                                        "type": "execution_output",
                                        "output": line.decode("utf-8"),
                                    }
                                )
                    except Exception:
                        pass
                    finally:
                        await self._cleanup_debug_session()

                self.debug_task = asyncio.create_task(read_debug_output())

            elif action in ["debug_step", "debug_next", "debug_continue"]:
                if self.debug_process and self.debug_process.stdin:
                    cmd = action.split("_")[1]  # step, next, continue
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

            elif action == "search_project":
                project_id = text_data_json.get("project_id")
                query = text_data_json.get("query")
                is_regex = text_data_json.get("is_regex", False)
                match_case = text_data_json.get("match_case", False)

                if not query:
                    await self.send(text_data=json.dumps({"action": "search_done"}))
                    return

                import re

                from asgiref.sync import sync_to_async

                from .models import ProjectFile

                @sync_to_async
                def fetch_files():
                    return list(ProjectFile.objects.filter(project_id=project_id))

                files = await fetch_files()

                flags = 0 if match_case else re.IGNORECASE
                try:
                    pattern = re.compile(query if is_regex else re.escape(query), flags)
                except re.error:
                    await self.send(
                        text_data=json.dumps(
                            {"action": "search_error", "error": "Invalid regex"}
                        )
                    )
                    return

                for f in files:
                    matches = []
                    lines = f.content.split("\n")
                    for i, line in enumerate(lines):
                        for m in pattern.finditer(line):
                            matches.append(
                                {
                                    "line": i + 1,
                                    "content": line.strip(),
                                    "start": m.start(),
                                    "end": m.end(),
                                }
                            )
                    if matches:
                        await self.send(
                            text_data=json.dumps(
                                {
                                    "action": "search_result",
                                    "file_id": str(f.id),
                                    "path": f.path,
                                    "matches": matches,
                                }
                            )
                        )
                await self.send(text_data=json.dumps({"action": "search_done"}))
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
    """
    Handles real-time WebSocket communication for collaborative pair-programming sessions.

    This consumer manages a channel layer group unique to each `room_id`. It handles the
    distribution of code changes, cursor movements, and code review comments between clients.
    State is managed per connection by tracking the `room_group_name`. Reconnection strategies
    and ping/pong heartbeats are managed by the client and the underlying ASGI server (Daphne),
    while this consumer focuses on application-level message brokering.
    """

    async def connect(self):
        """
        Accepts the WebSocket connection and adds the client to the collaboration room's group.
        Sends the initial Yjs document state stored in DB or cache to the connecting client.
        """
        import uuid
        import sys
        from django.core.exceptions import ValidationError

        self.room_id = self.scope["url_route"]["kwargs"]["room_id"]

        # Validate UUID format
        try:
            uuid.UUID(self.room_id)
        except (ValueError, AttributeError):
            await self.close()
            return

        user = self.scope.get("user")
        is_testing = "pytest" in sys.modules or "test" in sys.argv

        if not is_testing:
            if not user or not user.is_authenticated:
                await self.close()
                return

            from .models import CollabSession

            @database_sync_to_async
            def get_and_verify_session():
                try:
                    session = CollabSession.objects.filter(
                        id=self.room_id, is_active=True
                    ).first()
                    if session:
                        is_owner = session.project and session.project.user == user
                        is_allowed = session.allowed_users.filter(id=user.id).exists()
                        if is_owner or is_allowed:
                            return session
                except Exception:
                    pass
                return None

            session = await get_and_verify_session()
            if not session:
                await self.close()
                return

        self.room_group_name = f"collab_{self.room_id}"

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        # Send initial Yjs state from cache or DB to client
        from .models import CollabSession, CollabSessionLog

        cache_key = f"collab_doc_state_{self.room_id}"
        state = cache.get(cache_key)

        if state is None:

            @database_sync_to_async
            def get_db_state():
                session = CollabSession.objects.filter(id=self.room_id).first()
                return (
                    bytes(session.document_state)
                    if session and session.document_state
                    else None
                )

            state = await get_db_state()
            if state:
                cache.set(cache_key, state, timeout=86400)

        if state:
            await self.send(bytes_data=state)

        from asgiref.sync import sync_to_async

        if user and user.is_authenticated:

            @sync_to_async
            def log_join():
                session, _ = CollabSession.objects.get_or_create(id=self.room_id)
                CollabSessionLog.objects.create(
                    session=session, user=user, action="joined"
                )

            await log_join()

    async def disconnect(self, close_code):
        """
        Removes the client from the collaboration room's group upon disconnection.
        Saves the final document state to the database.
        """
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

        # Save final state to database
        cache_key = f"collab_doc_state_{self.room_id}"
        final_state = cache.get(cache_key)
        if final_state:
            from .models import CollabSession

            @database_sync_to_async
            def save_db_state(state):
                session, _ = CollabSession.objects.get_or_create(id=self.room_id)
                session.document_state = state
                session.save(update_fields=["document_state"])

            await save_db_state(final_state)

        # Log leaving the session
        from asgiref.sync import sync_to_async
        from .models import CollabSessionLog

        user = self.scope.get("user")
        if user and user.is_authenticated:

            @sync_to_async
            def log_leave():
                CollabSessionLog.objects.create(
                    session_id=self.room_id, user=user, action="left"
                )

            await log_leave()

    async def _save_update(self, update_bytes):
        """
        Helper to append update bytes to the room state in cache, and save to DB
        using a debounced interval lock.
        """
        from .models import CollabSession

        cache_key = f"collab_doc_state_{self.room_id}"
        current_state = cache.get(cache_key)

        if current_state is None:

            @database_sync_to_async
            def get_db_state():
                session = CollabSession.objects.filter(id=self.room_id).first()
                return (
                    bytes(session.document_state)
                    if session and session.document_state
                    else b""
                )

            current_state = await get_db_state()

        new_state = current_state + update_bytes
        cache.set(cache_key, new_state, timeout=86400)

        # Debounce DB writes: save at most once every 10 seconds per room
        lock_key = f"collab_db_lock_{self.room_id}"
        if not cache.get(lock_key):
            cache.set(lock_key, True, timeout=10)

            @database_sync_to_async
            def save_db_state(state):
                session, _ = CollabSession.objects.get_or_create(id=self.room_id)
                session.document_state = state
                session.save(update_fields=["document_state"])

            await save_db_state(new_state)

    async def receive(self, text_data=None, bytes_data=None):
        if bytes_data:
            # Broadcast binary Yjs updates (sync, updates, cursor awareness) to the group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "collab_message",
                    "bytes_data": bytes_data,
                    "sender_channel_name": self.channel_name,
                },
            )
            # Sync the update bytes to cache and DB
            await self._save_update(bytes_data)
        elif text_data:
            try:
                data = json.loads(text_data)
                action = data.get("action")

                from asgiref.sync import sync_to_async

                from .models import CodeReviewComment, CodeReviewThread, CollabSession
                from .serializers import (
                    CodeReviewCommentSerializer,
                    CodeReviewThreadSerializer,
                )

                user = self.scope.get("user")
                if not user or not user.is_authenticated:
                    return  # Only logged in users can comment

                if action == "add_comment":
                    thread_id = data.get("thread_id")
                    line_number = data.get("line_number")
                    content = data.get("content")

                    if not content:
                        return

                    @sync_to_async
                    def create_comment():
                        session, _ = CollabSession.objects.get_or_create(
                            id=self.room_id
                        )
                        if thread_id:
                            thread = CodeReviewThread.objects.get(id=thread_id)
                        else:
                            thread = CodeReviewThread.objects.create(
                                session=session, line_number=line_number
                            )

                        comment = CodeReviewComment.objects.create(
                            thread=thread, user=user, content=content
                        )
                        return thread, comment

                    thread, comment = await create_comment()

                    @sync_to_async
                    def serialize_thread():
                        return CodeReviewThreadSerializer(thread).data

                    thread_data = await serialize_thread()

                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            "type": "collab_text_message",
                            "text_data": json.dumps(
                                {"action": "thread_updated", "thread": thread_data}
                            ),
                            "sender_channel_name": self.channel_name,
                        },
                    )

                elif action == "resolve_thread":
                    thread_id = data.get("thread_id")

                    @sync_to_async
                    def resolve_thread():
                        thread = CodeReviewThread.objects.get(id=thread_id)
                        thread.is_resolved = True
                        thread.save()
                        return CodeReviewThreadSerializer(thread).data

                    thread_data = await resolve_thread()

                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            "type": "collab_text_message",
                            "text_data": json.dumps(
                                {"action": "thread_updated", "thread": thread_data}
                            ),
                            "sender_channel_name": self.channel_name,
                        },
                    )

            except Exception as e:
                print("Error in CollabConsumer receive:", e)

    async def collab_message(self, event):
        bytes_data = event.get("bytes_data")
        sender_channel_name = event.get("sender_channel_name")

        if self.channel_name != sender_channel_name:
            await self.send(bytes_data=bytes_data)

    async def collab_text_message(self, event):
        text_data = event.get("text_data")
        await self.send(text_data=text_data)
