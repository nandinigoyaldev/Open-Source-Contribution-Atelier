# Local Development Troubleshooting FAQ

This guide covers common setup issues when developing locally on Windows and macOS.

## Windows PowerShell, Command Prompt, and Bash

Commands differ between shells. Use the equivalent command for your environment.

| Task                        | Bash / macOS          | PowerShell                                 | Command Prompt             |
| --------------------------- | --------------------- | ------------------------------------------ | -------------------------- |
| Copy a file                 | `cp file .env`        | `Copy-Item file .env`                      | `copy file .env`           |
| Remove `node_modules`       | `rm -rf node_modules` | `Remove-Item node_modules -Recurse -Force` | `rmdir /s /q node_modules` |
| Set an environment variable | `export KEY=value`    | `$env:KEY="value"`                         | `set KEY=value`            |
| List files                  | `ls`                  | `Get-ChildItem`                            | `dir`                      |

If a Bash command fails in PowerShell or Command Prompt, use its platform equivalent rather than changing project files.

## Backend `.env` Setup

Copy [`backend/.env.example`](../backend/.env.example) to `backend/.env`. The file has two parts:

* **Part 1: required for local dev** (`DEBUG`, `DJANGO_ENV`, `SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`, CORS and `FRONTEND_URL`). Check these first.
* **Part 2: optional, by feature** (OAuth, GitHub App, Stripe, email, web push, backups, S3, AI tutor, Sentry). Each block says what happens when it is left blank, so you can skip any feature you are not working on.

Common startup errors:

* `SECRET_KEY environment variable is not set`: `SECRET_KEY=` is present but empty. Give it a value or delete the line.
* `Refusing to start: DEBUG=True while DJANGO_ENV=production`: use `DJANGO_ENV=development` locally.
* `Invalid CORS origin` / `Insecure CORS origin`: with `DEBUG=False`, every entry in `CORS_ALLOWED_ORIGINS` needs `http://` or `https://` and no `*`.
* Backend hangs on startup or reports a database connection error: `DATABASE_URL` points at a Postgres that is not running. Start Postgres, or comment the line out to use SQLite (`backend/db.sqlite3`).
* Redis connection warnings: safe to ignore locally. The backend automatically falls back to in-memory channels and cache. Set `FORCE_INMEMORY_CHANNEL_LAYER=1` to skip the channel/cache Redis check.

## Redis Fallback Behavior for Local Development

Redis is **not required** for local development. By default, the backend automatically detects whether Redis is available and falls back to in-memory handling for channels, caching, and rate limiting.

### Default Local Behavior

When you run the default local development server (`python manage.py runserver`) without Redis running:

1. **Auto-Detection**: On startup, Django checks whether Redis is reachable at `REDIS_URL` (which defaults to checking `redis://127.0.0.1:6379/0` if `REDIS_URL` is empty).
2. **Graceful Fallback**: If Redis cannot be reached, the server logs a warning and automatically configures in-memory alternatives:
   * **Django Channels**: Uses `channels.layers.InMemoryChannelLayer` for WebSocket routing and group messaging.
   * **Django Cache**: Uses `django.core.cache.backends.locmem.LocMemCache` for both the default cache (`atelier-unique-cache`) and the L1 memory cache (`atelier-l1-cache`).
   * **Rate Limiting**: Defaults to the `"local"` memory backend instead of Redis.
3. The server starts normally. WebSocket connections (such as real-time notifications or chat) and caching work out of the box within the local process.

### Silencing the Startup Warning

When Redis is not running, you will see a warning in your backend terminal on startup:

```text
WARNING: Redis unavailable (127.0.0.1:6379) — falling back to InMemoryChannelLayer and LocMemCache. WebSockets still work in this process; multi-worker fan-out requires Redis. Set REDIS_URL when Redis is ready, or FORCE_INMEMORY_CHANNEL_LAYER=1 to silence auto-detection.
```

This warning is safe to ignore during local development.

To silence the connection check and skip the probe on startup:

1. In `backend/.env`, set:
   ```bash
   FORCE_INMEMORY_CHANNEL_LAYER=1
   ```
2. Restart `python manage.py runserver`. The backend will immediately use the in-memory channel layer and local cache without running the channel/cache Redis probe. Rate-limit configuration still performs its separate Redis availability check.

### Documented Environment Variables

The following environment variables configured in `backend/config/settings.py` control Redis and in-memory behavior:

| Variable | Default (Local Setup) | Description |
| :--- | :--- | :--- |
| `REDIS_URL` | `redis://localhost:6379/0` (in `backend/.env.example`) | Redis connection URL. If unset or Redis is unreachable, Django automatically falls back to in-memory mode. |
| `FORCE_INMEMORY_CHANNEL_LAYER` | Unset / `0` | When set to `1` (or `true`, `yes`, `on`), bypasses the channel/cache Redis probe and forces `InMemoryChannelLayer` and `LocMemCache`. |
| `RATE_LIMIT_BACKEND` | `redis` (only if `REDIS_URL` is set and reachable) / `local` | Backend for rate limiting. Defaults to `redis` only when `REDIS_URL` is set and Redis is reachable; otherwise `local`. Set this variable to override the default. |

### Multi-Worker Limitations

The in-memory fallback is designed for single-process local development. It has the following limitations:

* **Single Process Only**: `InMemoryChannelLayer` and `LocMemCache` store channel groups and cached data in local process memory. Data cannot cross operating system process boundaries.
* **No Cross-Worker Fan-Out**: In a multi-worker setup (such as production servers with multiple Gunicorn/Uvicorn workers, Daphne web server running alongside Celery background workers, or scaled container clusters):
  * WebSocket messages broadcast in one worker cannot reach client connections held by another worker.
  * Channels group broadcasts (e.g. real-time notification alerts, leaderboard updates) require a shared message broker like Redis to reach all workers.
* **Cache Isolation**: `LocMemCache` is isolated to each worker process; cache updates or invalidations made in one process are not visible to other processes.
* **When Redis Is Required**: If you are testing background worker tasks (such as Celery/worker containers) communicating via Channels or running multi-worker deployments, start Redis (e.g., `docker compose up redis` or a local Redis service) and ensure `REDIS_URL` points to it.

## Node.js and Python Version Mismatches

Check the versions being used:

```bash
node --version
npm --version
python --version
```

Use the versions specified by the project when available. Version managers can help switch between projects:

* Node.js: `nvm` or `nvm-windows`
* Python: `pyenv` where supported, or the project's virtual environment

After changing runtime versions, reinstall dependencies if necessary.

## Port 5173 or 8000 Is Already in Use

The frontend commonly uses port `5173` and the backend may use port `8000`.

### Windows

```powershell
Get-NetTCPConnection -LocalPort 5173
Get-NetTCPConnection -LocalPort 8000
```

To identify the owning process:

```powershell
Get-NetTCPConnection -LocalPort 5173 | Select-Object OwningProcess
Get-Process -Id <PID>
```

Replace `<PID>` with the process ID returned by the first command.

### macOS

```bash
lsof -i :5173
lsof -i :8000
```

Stop a process only when you know it is safe to terminate, such as an old development server. Alternatively, use another available port if supported by the project's tooling.

## Native Dependency Build Failures

Packages such as `sharp`, `bcrypt`, and `psycopg` may require compatible runtimes or platform-specific build dependencies.

First verify the project's required Node.js or Python version. If dependencies are corrupted, reinstall them.

PowerShell:

```powershell
Remove-Item node_modules -Recurse -Force
npm install
```

Bash / macOS:

```bash
rm -rf node_modules
npm install
```

For Python packages such as `psycopg`, verify the project's Python version and required system dependencies before retrying.

## `node_modules` Permission Errors

If dependency installation or removal fails:

1. Stop development servers that may be using the files.
2. Retry from the project directory.
3. On Windows, check whether another process is locking the files.
4. Reinstall dependencies if the installation is corrupted.

Avoid using administrator privileges or `sudo` unless the project documentation specifically requires them.

## Where to Look in Logs

When troubleshooting, look at the first meaningful error rather than only the final stack trace.

Check:

* Frontend and backend terminal output
* Browser DevTools **Console**
* Browser DevTools **Network** tab for failed API requests
* `npm install` or Python dependency installation output
* Backend application logs
* Operating-system process information for port and permission issues

When asking for help, include the command that produced the error and the relevant error message.

## Paste This Debug Info

Use this template when opening an issue or asking maintainers for help:

```text
OS:
OS version:

Shell:
Shell version:

Node.js:
npm:
Python:
Package manager:

Frontend command:
Backend command:

Frontend port:
Backend port:

Exact command that failed:

Exact error message:

What I already tried:
```

Never include API keys, passwords, tokens, `.env` contents, or other secrets in logs or issue reports.
