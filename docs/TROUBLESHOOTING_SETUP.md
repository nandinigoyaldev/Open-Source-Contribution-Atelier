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
* Redis connection warnings: safe to ignore locally. The backend falls back to in-memory channels and cache. Set `FORCE_INMEMORY_CHANNEL_LAYER=1` to skip the Redis check.

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
