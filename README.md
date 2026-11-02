---
title: Open Source Contribution Atelier Backend
emoji: 🚀
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Open Source Contribution Atelier

> A hands-on space for learning how open source actually works—one fork, commit, review, and pull request at a time.

[Live app](https://open-source-contribution-atelier.vercel.app) · [API](https://nandinigoyaldev-atelier-backend.hf.space) · [Contributing](CONTRIBUTING.md) · [Report an issue](https://github.com/nandinigoyaldev/Open-Source-Contribution-Atelier/issues)

![React](https://img.shields.io/badge/React_19-20232A?logo=react&logoColor=61DAFB) ![Django](https://img.shields.io/badge/Django_5-092E20?logo=django) ![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white) [![License](https://img.shields.io/github/license/nandinigoyaldev/Open-Source-Contribution-Atelier)](LICENSE)

## Why Atelier?

Open source can feel intimidating before you make your first contribution. Atelier turns the workflow into something you can practice: explore the curriculum, work through Git scenarios safely, get feedback, and build a record of progress as you go.

| Learn                                        | Practice                                           | Grow                                                        |
| -------------------------------------------- | -------------------------------------------------- | ----------------------------------------------------------- |
| Modular lessons, quizzes, and Git explainers | Interactive Git sandboxes and conflict simulations | XP, badges, certificates, peer review, and community spaces |

## What’s inside

- A Markdown-driven curriculum for Git, GitHub, collaboration, reviews, and contribution etiquette.
- Interactive sandboxes for branches, rebases, conflicts, bisects, stashes, and more.
- Progress tracking, streaks, badges, certificates, and learning paths.
- Peer-review and community features, plus real-time collaboration where configured.
- A Django REST API with JWT authentication and an accessible React 19 frontend.

## Stack

| Layer          | Built with                                                                            |
| -------------- | ------------------------------------------------------------------------------------- |
| Frontend       | React 19, TypeScript, Vite, Tailwind CSS, React Router, Redux Toolkit, TanStack Query |
| Backend        | Django 5, Django REST Framework, Django Channels, Celery                              |
| Local services | SQLite by default; Postgres and Redis with Docker                                     |
| Quality        | Vitest, Playwright, Pytest, ESLint, Prettier, Black                                   |

## Run it locally

**Prerequisites:** Node 20+, Python 3.9+, and `make` (optional but helpful).

```bash
git clone https://github.com/nandinigoyaldev/Open-Source-Contribution-Atelier.git
cd Open-Source-Contribution-Atelier
make setup
```

Start the API in one terminal:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate # Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_lessons
python manage.py seed_dashboard
python manage.py runserver
```

Start the app in another:

```bash
cd frontend
npm install
npm run dev
```

Open [localhost:5173](http://localhost:5173). The API is available at [localhost:8000/api](http://localhost:8000/api/).

> `make setup` copies the environment templates. You can also copy `backend/.env.example` and `frontend/.env.example` manually. OAuth sign-in needs the corresponding Google or GitHub credentials in those files.

### Docker

Prefer the whole stack at once?

```bash
docker compose up --build
```

That starts Postgres, Redis, Django, the notifications worker, and Vite. See the [Docker hot-reload guide](docs/DOCKER_HOT_RELOAD.md) for development mounts.

Database credentials come from `POSTGRES_DB`, `POSTGRES_USER` and `POSTGRES_PASSWORD`. The defaults work for local dev; to change them, copy `.env.example` to `.env` in the repo root. Use your own password anywhere outside local dev.

Keep these values to letters, digits, `-`, `_` and `.`, since they are inserted into `DATABASE_URL` without URL-encoding (characters such as `#`, `@`, `:`, `/` or `%` would break it). Postgres only applies them when the `postgres_data` volume is first created, so after changing them on an existing setup either run `docker compose down -v` (this wipes the local database) or update the role/password/database inside Postgres to match.

## Useful commands

| Area                   | Command                                                 |
| ---------------------- | ------------------------------------------------------- |
| Frontend checks        | `cd frontend && npm run lint && npm run test`           |
| Frontend build         | `cd frontend && npm run build`                          |
| Backend tests          | `cd backend && pytest`                                  |
| Format backend         | `cd backend && black . && isort .`                      |
| Check curriculum slugs | `cd backend && python manage.py check_curriculum_slugs` |
| Validate curriculum content | `python scripts/validate_curriculum.py` |

## Contribute

New contributors are welcome. Find a [`good first issue`](https://github.com/nandinigoyaldev/Open-Source-Contribution-Atelier/labels/good%20first%20issue), read the [contribution guide](CONTRIBUTING.md), then open a focused pull request.

- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Security policy](SECURITY.md)
- [Content guide](docs/CONTENT_GUIDE.md)
- [Architecture notes](docs/ARCHITECTURE.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Release checklist](docs/RELEASE_CHECKLIST.md) (maintainers)
- [Admin audit events](docs/AUDIT_EVENTS.md)
- [Local setup FAQ](docs/TROUBLESHOOTING_SETUP.md)
- [Contributor leaderboard](LEADERBOARD.md)

## License

Released under the [MIT License](LICENSE).
