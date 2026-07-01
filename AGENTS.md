# AGENTS.md

## Repo layout

- **backend/** — Django REST API (Python). Apps: `accounts`, `content`, `progress`, `challenges`, `sandbox`, `search`, `dashboard`, `notifications`.
- **frontend/** — React 19 SPA (TypeScript, Vite, Tailwind). Curriculum content lives in `frontend/public/content/`.
- **services/** — background workers (e.g. `notifications_worker` with Redis/Celery).
- **infra/** — architecture docs and maintainer playbook.

## Commands

### Backend (Python 3.9+)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_lessons && python manage.py seed_dashboard
python manage.py runserver        # http://localhost:8000/api/
python manage.py test             # or: pytest
```

Pre-commit hooks run `black` and `isort` on `backend/`. Format before pushing:
```bash
black . && isort .
```

Pyright config is at repo root (`pyrightconfig.json` with `extraPaths: ["backend"]`).

### Frontend (Node 20+)

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173/
npm run lint         # ESLint
npm run format       # Prettier
npm run test         # Vitest
npm run build        # tsc -b && vite build
```

E2E tests (Playwright): `npm run test:e2e` (from `frontend/`).

### Docker (full stack)

```bash
docker compose up --build
```

Boots Postgres, Redis, Django backend (:8000), and Vite frontend (:5173).

## Pre-push checklist (order matters)

1. `cd frontend && npm run lint`
2. `cd frontend && npm run format:check`
3. `cd frontend && npm run test`
4. `cd backend && black --check .`
5. `cd backend && pytest`

## Available skills (`.agents/skills/`)

| Skill | What it does in this repo |
|---|---|
| `conventional-commit` | Generates standardized commit messages following Conventional Commits spec (`feat/fix/chore` format). Reads your diff, builds the message, runs `git commit` for you. |
| `docker-expert` | Optimizes and debugs the repo's `Dockerfile` and `docker-compose.yml`. Covers multi-stage builds, image size, security hardening, and production deployment patterns. |
| `python-design-patterns` | Reviews and guides Django backend code structure — KISS, single responsibility, composition over inheritance. Use when refactoring apps like `accounts`, `content`, or `sandbox`. |
| `python-observability` | Adds structured logging, Prometheus metrics, and distributed tracing to Django backend services. Use when debugging prod issues or wiring up a new app. |

## Key quirks

- Django defaults to **SQLite** locally; Docker uses **Postgres**. The `.env.example` files have sane defaults — copy them to `.env`.
- Backend settings module: `config.settings` (set in `pytest.ini` and `render.yaml`).
- The sandbox exercise verifier only accepts whitelisted Git-learning commands. Don't extend it without reviewing the allowlist.
- Frontend content (lessons, modules, quizzes) is purely Markdown + `curriculum.json` in `public/content/`. Adding content requires **zero code changes** — see `docs/CONTENT_GUIDE.md`.
- Branch naming: `feat/...`, `fix/...`, `docs/...`, `refactor/...`.
- PR template lives at `.github/pull_request_template.md`.
