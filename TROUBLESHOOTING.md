# Troubleshooting: Docker Compose Setup Failures

This guide helps contributors quickly resolve common failures when running the project with Docker Compose.

## Quick start (expected)

From the repo root:

```bash
docker compose up --build
```

If something fails, use the sections below to identify the issue.

---

## 1) Port conflicts (EADDRINUSE / “port is already allocated”)

### Symptoms
- `EADDRINUSE`
- errors mentioning one of these ports:
  - `5432` (Postgres)
  - `6379` (Redis)
  - `8000` (backend routing / proxying)
  - `80` / `8080` (Traefik)

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

## Reference
- `docker-compose.yml` (dev): root-level Compose configuration
- `docker-compose.prod.yml` (prod): Compose configuration for production-style runs

