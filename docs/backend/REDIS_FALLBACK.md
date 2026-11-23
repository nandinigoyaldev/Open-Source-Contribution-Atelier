# Local Redis Fallback & Resilient Channels Guide

## 1. Overview & Architecture

Redis is **optional** for local standalone development. When running the Django development server (`python manage.py runserver`), developers can work on core features (lessons, progress tracking, challenges, auth, REST APIs) without installing or running a local Redis server.

To achieve zero-friction local onboarding while preserving high-availability production behavior, CampusConnect uses a two-tier resilience architecture:

```
┌──────────────────────────────────────────────────────────────┐
│                    Application Startup                       │
│              (config.channel_layers.py)                      │
└──────────────────────────────┬───────────────────────────────┘
                               │
            Is FORCE_INMEMORY_CHANNEL_LAYER=1?
                               │
            ┌──────────────────┴──────────────────┐
           Yes                                   No
            │                                     │
            ▼                                     ▼
   [InMemoryChannelLayer]               Is Redis reachable?
   + [LocMemCache]                                │
   (Skip network probe)             ┌─────────────┴─────────────┐
                                   Yes                          No
                                    │                           │
                                    ▼                           ▼
                        [ResilientChannelLayer]       [InMemoryChannelLayer]
                        (Wraps RedisChannelLayer)     + [LocMemCache]
                                    │                 (Startup fallback)
                           Redis dies at runtime?
                                    │
                                   Yes
                                    ▼
                        [Degrade to InMemory]
                        (Per-process failover)
```

1. **Startup Auto-Detection**: Checks whether Redis is available at `REDIS_URL` (defaulting to `redis://127.0.0.1:6379/0`). If unreachable, it falls back to in-memory channels and caches.
2. **Forced In-Memory**: Setting `FORCE_INMEMORY_CHANNEL_LAYER=1` skips the network connection check entirely, immediately activating the in-memory backend and silencing startup warnings.
3. **Runtime Failover (`ResilientChannelLayer`)**: If Redis was available at startup but fails mid-process, `ResilientChannelLayer` catches the failure, closes the dying Redis socket pools (bounded by a 5.0-second timeout), and switches that process to `InMemoryChannelLayer` without crashing active WebSocket consumers.

---

## 2. When the Fallback is Used

The in-memory fallback is automatically engaged in three scenarios:

### Scenario A: Startup Auto-Detection (Redis Down)
When `python manage.py runserver` boots and Redis is not running on `REDIS_URL`:
- `config.channel_layers.is_redis_available()` attempts a `PING` (or TCP socket connection with a 0.5s timeout).
- If connection fails or times out, the backend logs:
  ```text
  WARNING: Redis unavailable (127.0.0.1:6379) — falling back to InMemoryChannelLayer and LocMemCache. WebSockets still work in this process; multi-worker fan-out requires Redis. Set REDIS_URL when Redis is ready, or FORCE_INMEMORY_CHANNEL_LAYER=1 to silence auto-detection.
  ```
- The backend initializes `InMemoryChannelLayer`, `LocMemCache`, and defaults `RATE_LIMIT_BACKEND` to `"local"`.

### Scenario B: Explicitly Forced via Environment
When `FORCE_INMEMORY_CHANNEL_LAYER=1` is configured in `backend/.env`:
- Auto-detection is bypassed completely (no TCP or PING probe).
- The server boots immediately with `InMemoryChannelLayer` and `LocMemCache`.
- The startup warning is suppressed, replaced by:
  ```text
  WARNING: FORCE_INMEMORY_CHANNEL_LAYER is set — using InMemoryChannelLayer (realtime fan-out is single-process only).
  ```

### Scenario C: Runtime Mid-Process Redis Failure
When Redis was connected at startup, but crashes, restarts, or loses network connectivity while the server is running:
- Any channel layer call (`send`, `group_send`, `group_add`, `group_discard`) in `ResilientChannelLayer` encounters a `ConnectionError` or socket timeout.
- The resilient layer marks the instance as `degraded = True`, switches `self._active = self._fallback`, and logs:
  ```text
  WARNING: Channels Redis failed during <operation> (<Error>: <details>). Falling back to InMemoryChannelLayer for this process. Realtime messages will not cross workers until Redis is restored and this process fails back (see try_failback) or is restarted.
  ```
- Redis socket connection pools are cleaned up asynchronously (`close_pools()`) with a 5.0s timeout to prevent socket leaks.
- WebSocket consumers continue executing on the in-memory layer rather than raising unhandled 500 errors.
- Once Redis answers a `PING` again (probed at most every 15 seconds) and no connection is subscribed on the fallback, the layer switches back to Redis by itself. While connections are still subscribed it stays degraded, because switching would strand them. See [DISASTER_RECOVERY.md](../DISASTER_RECOVERY.md).

---

## 3. How to Force the In-Memory Fallback

To bypass startup probes, speed up local boots, or run tests without Redis:

1. Open `backend/.env` (or set environment variables in your terminal):
   ```bash
   FORCE_INMEMORY_CHANNEL_LAYER=1
   ```
   *(Values `1`, `true`, `yes`, and `on` are treated as truthy; case-insensitive).*

2. Restart the Django development server:
   ```bash
   python manage.py runserver
   ```

### Effects of Forcing In-Memory Mode
- **Channels**: `CHANNEL_LAYERS["default"]["BACKEND"]` becomes `channels.layers.InMemoryChannelLayer`.
- **Caches**: `CACHES["default"]` and `CACHES["l1_memory"]` use `django.core.cache.backends.locmem.LocMemCache`.
- **Rate Limiting**: `RATE_LIMIT_BACKEND` defaults to `"local"` because `is_redis_available()` returns `False` immediately without probing.
- **Auto-Detection Silenced**: Startup connection delays and unavailable Redis warning logs are eliminated.

---

## 4. WebSocket & Realtime Limitations

While HTTP endpoints and basic local single-tab WebSocket connections function under `InMemoryChannelLayer`, **in-memory channel layers have fundamental architectural limitations**:

> [!WARNING]
> In-memory channels store channel groups and messages in local process memory (`dict`). They cannot cross operating system process boundaries.

### 1. No Cross-Worker or Cross-Container Fan-Out
- In local development with `runserver`, WebSockets work within that single process.
- In multi-worker architectures:
  - **Docker Compose**: The `backend` web service and `worker` (Celery / Django-Q / notification worker) service run in separate containers and separate OS processes.
  - **Production**: Multiple Gunicorn/Uvicorn/Daphne workers run in separate processes.
- **Symptom**: An asynchronous task running in a Celery worker (e.g., generating an achievement badge or a progress update) calls `safe_group_send_sync("notifications_<user_id>", {...})`. With `InMemoryChannelLayer`, that message is placed in the *worker's* memory dictionary. The client connected via WebSocket to the *web server* process **never receives the message**.

### 2. Client Degradation on Mid-Process Failover
- When `ResilientChannelLayer` degrades to in-memory mode, or when group registration fails:
  - WebSocket consumers in `apps.notifications.consumers` (`NotificationConsumer`, `LeaderboardConsumer`) detect the degradation via `channel_safety.safe_group_add`.
  - The server sends a connection payload containing `"degraded": true`:
    ```json
    {
      "type": "connection_established",
      "degraded": true,
      "message": "Realtime updates degraded; please poll HTTP endpoints."
    }
    ```
  - Frontend clients receiving `"degraded": true` must fall back to periodic HTTP polling (e.g. `GET /api/notifications/` or `GET /api/leaderboard/`).

### 3. Ephemeral State and Zero Message Persistence
- Any channel group subscriptions or pending channel messages held in `InMemoryChannelLayer` are immediately lost whenever the web process restarts or Django's auto-reloader detects code changes.

### 4. Cache Partitioning
- In-memory cache (`LocMemCache`) is also per-process. A cache write or invalidation in one process is invisible to any other process or worker.

---

## 5. How to Verify Redis Connectivity Locally

Before troubleshooting WebSocket or cache issues, verify that Redis is reachable from your environment:

### Method 1: Using `redis-cli` (Recommended)

**For Local Standalone Redis:**
```bash
redis-cli -u redis://127.0.0.1:6379/0 ping
```
*Expected response:*
```text
PONG
```

**For Docker Compose Redis:**
```bash
docker compose exec redis redis-cli ping
```
*Expected response:*
```text
PONG
```

---

### Method 2: Using Django Shell & Project Helpers

Verify that Django's built-in detection helper accepts the connection:

```bash
cd backend
python manage.py shell -c "from config.channel_layers import is_redis_available; print('Redis available:', is_redis_available('redis://127.0.0.1:6379/0'))"
```
*Expected output when Redis is up:*
```text
Redis available: True
```

---

### Method 3: Using a Quick Python Script

Test connection via the `redis` client package directly:

```bash
python -c "import redis; r = redis.from_url('redis://127.0.0.1:6379/0'); print(r.ping())"
```
*Expected output:*
```text
True
```

---

### Method 4: Network Port Probing (Cross-Platform)

If command-line tools are not installed, test whether port `6379` is open:

**Windows PowerShell:**
```powershell
Test-NetConnection -ComputerName 127.0.0.1 -Port 6379
```
*Look for:* `TcpTestSucceeded : True`

**Linux / macOS:**
```bash
nc -zv 127.0.0.1 6379
# or
timeout 1 bash -c "</dev/tcp/127.0.0.1/6379" && echo "Port 6379 is open"
```

---

## 6. Environment Variables Reference

| Variable | Default (Local) | Default (Docker) | Purpose |
| :--- | :--- | :--- | :--- |
| `REDIS_URL` | `redis://localhost:6379/0` | `redis://redis:6379/0` | Primary Redis connection string. If unreachable, the server falls back to in-memory mode. |
| `FORCE_INMEMORY_CHANNEL_LAYER` | *Unset* | *Unset* | Set to `1`, `true`, `yes`, or `on` to bypass connection checks and force `InMemoryChannelLayer` + `LocMemCache`. |
| `RATE_LIMIT_BACKEND` | `local` (if Redis down) | `redis` | Selects rate limiting backend. Defaults to `redis` only when `REDIS_URL` is set and Redis accepts a PING. |

---

## 7. Related Documentation & Troubleshooting Links

- **Setup & Standalone Troubleshooting**: [`docs/TROUBLESHOOTING_SETUP.md`](../TROUBLESHOOTING_SETUP.md#redis-fallback-behavior-for-local-development)
- **Docker Compose Failures**: [`docs/TROUBLESHOOTING.md`](../TROUBLESHOOTING.md#4b-redis-down--channels-websocket-crashes)
- **Architecture Overview**: [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md)
- **Worker Recovery & Ledger**: [`docs/WORKER_RECOVERY.md`](../WORKER_RECOVERY.md)
- **Maintainer Playbook**: [`AGENTS.md`](../../AGENTS.md)
