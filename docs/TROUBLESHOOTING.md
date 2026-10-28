# Troubleshooting: Docker Compose Setup Failures

This guide helps contributors quickly resolve common failures when running the project with Docker Compose.

## Quick start (expected)

From the repo root:

```bash
# 1. Bootstrap all required environment files
make setup
# or: make env

# 2. Build and start containers
docker compose up --build
```

If something fails, use the sections below to identify the issue.

---

## 0) Missing environment files (`.env` / `docker-compose.override.yml`)

### Symptoms
- Backend or frontend fails to start with errors about missing environment variables.
- Docker Compose fails to read configuration settings or hot-reloading does not trigger.

### Fix
Run the automated setup target to copy all example environment files:
```bash
make setup
# or: make env
```
Or manually copy the files:
```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
cp docker-compose.override.yml.example docker-compose.override.yml
```

---

## 1) Port conflicts (EADDRINUSE / “port is already allocated”)

### Symptoms
- `EADDRINUSE`
- errors mentioning one of these ports:
  - `5432` (Postgres)
  - `6379` (Redis)
  - `8000` (backend routing / proxying)
  - `80` (Traefik); `8080` only if you opted in to the dashboard with `docker-compose.dev.yml`

### Check what is using the port
On Windows, you can identify the owning process:

```bash
netstat -ano | findstr :5432
netstat -ano | findstr :6379
netstat -ano | findstr :8000
netstat -ano | findstr :80
```

Then stop the conflicting service/process in Task Manager (or via services.msc).

### Fix options
- **Preferred:** stop/disable the conflicting local service.
- **Alternative:** change the host ports in `docker-compose.yml` (the left side of `HOST:CONTAINER`, e.g. `"5432:5432"`).
  - If you change ports, update any docs/env that refer to the original ports.

---

## 2) Postgres startup delays / database not ready

### Symptoms
- Backend/worker logs show connection errors such as:
  - `could not connect to server`
  - `connection refused`
  - `FATAL: remaining connection slots are reserved`
  - timeouts when accessing DB during migrations

### Why it happens
Postgres may take a moment to initialize (especially on first run or after clearing volumes). Django migrations and the worker can attempt to connect while Postgres is still starting.

### Fix
1. View Postgres logs:
   ```bash
   docker compose logs -f db
   ```
2. If this is a first run or you suspect broken state, reset volumes:
   ```bash
   docker compose down -v
   docker compose up --build
   ```
3. Wait for Postgres to become healthy, then retry (restart is often enough):
   ```bash
   docker compose restart backend worker
   ```

---

## 3) Volume permission issues (permission denied / cannot write data)

### Symptoms
- Postgres errors writing to:
  - `/var/lib/postgresql/data`
- Messages like:
  - `permission denied`
  - `could not create directory`
  - container fails early and keeps restarting

### Fix
- Reset the persistent volume (common for local dev):
  ```bash
  docker compose down -v
  docker compose up --build
  ```
- If the issue persists, confirm Docker Desktop is running normally and that you are not mixing different Docker contexts/permissions.

---

## 4) Migrations failing (backend/worker exits immediately)

### Symptoms
- `backend` or `worker` repeatedly restarts.
- Logs show Django migration errors, such as:
  - missing tables
  - database schema mismatch
  - invalid env vars for `DATABASE_URL`

### Fix
1. Inspect logs:
   ```bash
   docker compose logs -f backend
   docker compose logs -f worker
   ```
2. Confirm environment variables are correct.
   - In `docker-compose.yml`, backend/worker use:
     - `DATABASE_URL=postgres://atelier_user:atelier_password@db:5432/atelier`
     - `REDIS_URL=redis://redis:6379/0`
3. If you changed migrations or the DB state is inconsistent, reset volumes:
   ```bash
   docker compose down -v
   docker compose up --build
   ```

---

## 4b) Redis down / Channels WebSocket crashes

### Symptoms
- Backend logs show Redis connection errors during WebSocket connect
- Realtime notifications / leaderboard fail hard when Redis is stopped

### Expected (after graceful fallback)
- If Redis is unreachable at startup, Channels uses **InMemoryChannelLayer** and LocMem cache (warning logged).
- If Redis dies later, the resilient layer switches to in-memory for that process (warning logged).
- WebSocket connections still accept; clients may see `"degraded": true` and should poll HTTP for inbox updates.

### Local development fallback & override

Redis is **optional** for local development. When running locally outside of Docker (e.g. `python manage.py runserver`), the backend automatically detects that Redis is unavailable and falls back to in-memory mode:
- **Channels**: `channels.layers.InMemoryChannelLayer`
- **Cache**: `django.core.cache.backends.locmem.LocMemCache`
- **Rate limiting**: `local` in-memory backend

To skip auto-detection and silence the startup warning:

```bash
# backend/.env
FORCE_INMEMORY_CHANNEL_LAYER=1
```

Restart the backend after changing this. This flag skips only the channel/cache Redis probe; rate-limit configuration still performs its separate Redis availability check.

### Relevant Environment Variables

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `REDIS_URL` | `redis://localhost:6379/0` (dev) / `redis://redis:6379/0` (Docker) | Target Redis connection string. |
| `FORCE_INMEMORY_CHANNEL_LAYER` | Unset | Set to `1` (or `true`) to bypass the channel/cache Redis check and force `InMemoryChannelLayer` + `LocMemCache`. |
| `RATE_LIMIT_BACKEND` | `redis` (only if `REDIS_URL` is set and reachable) / `local` | Backend for rate limiting. Defaults to `redis` only when `REDIS_URL` is set and Redis is reachable; otherwise `local`. Set this variable to override the default. |

### Multi-worker limitations

While single-process local development works without Redis, multi-worker architectures require Redis:
- **Single Process Only**: `InMemoryChannelLayer` and `LocMemCache` operate within a single process. They cannot share messages or state across multiple worker processes.
- **Docker Compose & Production**: In Docker Compose (where `backend` and `worker` run as separate containers) or production (with multi-worker WSGI/ASGI servers), WebSocket broadcasts from background workers or other processes cannot reach client connections without Redis.
- For full local testing with Docker Compose, ensure the `redis` service is running.

### Verify Redis connectivity

For a local Redis installation, run:

```bash
redis-cli -u redis://localhost:6379/0 ping
```

For the Docker Compose Redis service, run:

```bash
docker compose exec redis redis-cli ping
```

A healthy Redis instance should respond with:

```text
PONG
```

If Redis is unreachable, check that the Redis service is running and that `REDIS_URL` points to the correct host and port. In Docker Compose, the backend uses `redis://redis:6379/0`; for a local backend, `backend/.env.example` uses `redis://localhost:6379/0`. For standalone local development troubleshooting, see [`TROUBLESHOOTING_SETUP.md`](TROUBLESHOOTING_SETUP.md).

---

## 5) Traefik routing / services unreachable

### Symptoms
- Frontend loads fail in the browser.
- Backend endpoints not reachable.
- Healthchecks show failures.

### What to check
- Traefik container status:
  ```bash
  docker compose ps
  docker compose logs -f reverse-proxy
  ```
- Backend healthcheck in Compose targets:
  - `http://localhost:8000/api/`
- Frontend healthcheck in Compose targets:
  - `http://localhost:80/`

### Fix
- Ensure containers are running and healthy:
  ```bash
  docker compose ps
  ```
- If you changed ports/labels in `docker-compose.yml`, verify:
  - Traefik router rules (`PathPrefix(...)`)
  - backend service port mapping (`traefik.http.services.backend.loadbalancer.server.port=8000`)
  - frontend service port mapping (`traefik.http.services.frontend.loadbalancer.server.port=80`)

---

### Traefik dashboard

The dashboard is off by default because it has no authentication. To use it locally, start Compose with the dev override; it listens on `127.0.0.1:8080` only:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

## 6) Build failures (image build errors)

### Symptoms
- `docker compose up --build` fails during `backend` or `frontend` build.

### Fix
- Rebuild from scratch:
  ```bash
  docker compose build --no-cache
  docker compose up
  ```
- If `backend` fails, inspect:
  ```bash
  docker compose logs --tail=200 backend
  ```
- If `frontend` fails, inspect:
  ```bash
  docker compose logs --tail=200 frontend
  ```

---

## 7) Minimal “collect logs” checklist for reporting an issue

When opening a GitHub issue/PR discussion, include the following outputs:

```bash
docker compose ps

docker compose logs --tail=200 db
docker compose logs --tail=200 redis

docker compose logs --tail=200 backend
docker compose logs --tail=200 worker

docker compose logs --tail=200 reverse-proxy
```

Also include:
- OS version (Windows 11/macOS/Linux)
- Docker Desktop version
- The exact command you ran (e.g. `docker compose up --build`)
- Any error stack trace you saw in the terminal

---

## Invalid HTTP_HOST header / ImproperlyConfigured: ALLOWED_HOSTS

The backend reads `ALLOWED_HOSTS` from the environment (comma-separated). If it is unset it defaults to `localhost,127.0.0.1`.

- A `400 Bad Request` / "Invalid HTTP_HOST header" on a deployed backend (Vercel, Hugging Face Spaces, etc.) means the hostname is not in the list. Set `ALLOWED_HOSTS` to include it, e.g. `ALLOWED_HOSTS=localhost,127.0.0.1,your-space.hf.space,your-project.vercel.app`.
- A bare `*` is rejected at startup when `DEBUG=False`. List the real hostnames instead.

---

## Reference
- `docker-compose.yml` (dev): root-level Compose configuration
- `docker-compose.prod.yml` (prod): Compose configuration for production-style runs
- [`TROUBLESHOOTING_SETUP.md`](TROUBLESHOOTING_SETUP.md): Local development troubleshooting FAQ (Windows & macOS)
