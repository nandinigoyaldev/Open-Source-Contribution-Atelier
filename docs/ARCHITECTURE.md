# Architecture Overview

## WebSocket Communication

### CollabConsumer Lifecycle
The `CollabConsumer` handles complex state for pair programming sessions. It leverages Django Channels and Redis to broker messages between multiple clients in the same session.

- **Connection Setup**: Upon a new WebSocket connection, the consumer extracts the `room_id` from the URL kwargs. It then assigns the client's `channel_name` to a channel layer group uniquely named `collab_<room_id>`. The connection is then explicitly accepted.
- **Message Brokering**: 
  - **Binary Data (`bytes_data`)**: Forwarded immediately to all other participants in the room. This is optimized for fast, frequent updates like cursor position or keystrokes (e.g., Yjs/CRDT sync).
  - **Text Data (`text_data`)**: Parsed as JSON and routed according to its `action` field. Actions include `add_comment` or `resolve_thread` for code reviews, which interact directly with the database.
- **Disconnection**: The client's channel is discarded from the `room_group_name` to prevent broadcast errors.

### Heartbeats and Reconnection
- **Ping/Pong Heartbeats**: Real-time connections are kept alive via ping/pong frames automatically handled by the underlying ASGI server (Daphne/Uvicorn). No manual application-level pings are required.
- **Reconnection Strategy**: If a client disconnects unexpectedly, the frontend client (e.g., ReconnectingWebSocket or similar abstraction) is responsible for initiating a reconnection. The state (like cursor positions) is eventually consistent upon reconnection because the authoritative state is synced via CRDTs or fetched via REST APIs before binding to the WebSocket.
