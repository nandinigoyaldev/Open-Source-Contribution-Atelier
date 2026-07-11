
<br />

<div align="center">

<!-- Hero Banner -->
<img src="https://capsule-render.vercel.app/api?type=waving&color=0:FF6B6B,50:4ECDC4,100:45B7D1&height=220&section=header&text=Open%20Source%20Contribution%20Atelier&fontSize=36&fontColor=ffffff&animation=fadeIn&fontAlignY=35&desc=From%20Zero%20to%20Open%20Source%20Hero%20🚀&descAlignY=55&descSize=18" width="100%" />

<p><i>A complete Open Source Learning Platform designed to help beginners confidently transition from zero to real open-source contributions.</i></p>

<!-- Badges -->
[![Live Demo](https://img.shields.io/badge/🌐_Live_Demo-Vercel-000000?style=for-the-badge&logo=vercel&logoColor=white)](https://open-source-contribution-atelier.vercel.app)
[![Backend API](https://img.shields.io/badge/🤗_API-Hugging_Face-FFD21E?style=for-the-badge&logo=huggingface&logoColor=black)](https://nandinigoyaldev-atelier-backend.hf.space)
[![SSoC 2026](https://img.shields.io/badge/SSoC_2026-Participating-4ECDC4?style=for-the-badge&logo=opensourceinitiative&logoColor=white)](#)

[![GitHub Stars](https://img.shields.io/github/stars/nandinigoyaldev/Open-Source-Contribution-Atelier?style=flat-square&logo=github&label=Stars&color=FFD700)](https://github.com/nandinigoyaldev/Open-Source-Contribution-Atelier)
[![GitHub Forks](https://img.shields.io/github/forks/nandinigoyaldev/Open-Source-Contribution-Atelier?style=flat-square&logo=github&label=Forks&color=45B7D1)](https://github.com/nandinigoyaldev/Open-Source-Contribution-Atelier/fork)
[![GitHub Issues](https://img.shields.io/github/issues/nandinigoyaldev/Open-Source-Contribution-Atelier?style=flat-square&logo=github&label=Issues&color=FF6B6B)](https://github.com/nandinigoyaldev/Open-Source-Contribution-Atelier/issues)
[![GitHub PRs](https://img.shields.io/github/issues-pr/nandinigoyaldev/Open-Source-Contribution-Atelier?style=flat-square&logo=github&label=PRs&color=4ECDC4)](https://github.com/nandinigoyaldev/Open-Source-Contribution-Atelier/pulls)
[![License](https://img.shields.io/github/license/nandinigoyaldev/Open-Source-Contribution-Atelier?style=flat-square&color=purple)](LICENSE)

[![CI Checks](https://img.shields.io/github/actions/workflow/status/nandinigoyaldev/Open-Source-Contribution-Atelier/ci.yml?style=flat-square&logo=githubactions&logoColor=white&label=CI%20Checks)](https://github.com/nandinigoyaldev/Open-Source-Contribution-Atelier/actions)
[![React](https://img.shields.io/badge/React_19-61DAFB?style=flat-square&logo=react&logoColor=black)](#)
[![Django](https://img.shields.io/badge/Django_5.0-092E20?style=flat-square&logo=django&logoColor=white)](#)
[![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white)](#)
[![Tailwind](https://img.shields.io/badge/Tailwind_CSS-06B6D4?style=flat-square&logo=tailwindcss&logoColor=white)](#)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white)](#)

</div>

---

## ✨ Features

| Feature | Description |
|---|---|
| 🎮 **Gamified Curriculum** | 8 core modules going from mindset basics to advanced conflict resolution |
| 📝 **Interactive Quizzes** | Multiple-choice testing dashboards with instant feedback |
| 🏅 **Badges Cabinet** | Earn milestone rewards mapping directly to module progress |
| 📜 **Printable Certificates** | Gorgeous A4 neobrutalist certificate with verification hashes |
| 🏆 **Hall of Fame** | Cohort stats, active streak calendars, and GitHub contributor recognition |
| 📖 **Markdown-Driven Content** | Lessons are parsed dynamically — adding content requires zero code changes |
| 💬 **Real-Time Community Chat** | End-to-end encrypted WebSocket chat with typing indicators |
| 👥 **Peer Review System** | Submit code for review and earn XP by reviewing others |
| 🔍 **Interactive Sandbox** | Git terminal emulator with autocomplete and command replay |

---


## 🛠️ Technical Stack

<table>
<tr>
<td align="center" width="50%">

### ⚡ Frontend
React 19 · TypeScript · Vite · Tailwind CSS<br/>
React Router 7 · TanStack React Query · Redux Toolkit

</td>
<td align="center" width="50%">

### 🔧 Backend
Django 5.0 · Django REST Framework · Simple JWT<br/>
Django Channels · Celery · Redis · PostgreSQL

</td>
</tr>
<tr>
<td align="center">

### ☁️ Deployment
Vercel (Frontend) · Hugging Face (Backend API)<br/>
Neon (PostgreSQL) · Upstash (Redis)

</td>
<td align="center">

### 🧪 Testing & CI
Vitest · Playwright · Pytest<br/>
GitHub Actions CI · ESLint · Prettier · Black

</td>
</tr>
</table>

---

## 🚀 Quick Start (Local Development)

### 1. Setup Environment
```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

> [!WARNING]
> **Google OAuth login requires a valid `VITE_GOOGLE_CLIENT_ID` in `frontend/.env`.**
> Create credentials in the [Google Cloud Console](https://console.cloud.google.com/) with authorized redirect URIs set to `http://localhost:5173`.

> [!WARNING]
> **GitHub OAuth login requires GitHub OAuth credentials.**
> 1. Go to [GitHub OAuth Apps Settings](https://github.com/settings/developers)
> 2. Click "OAuth Apps" → "New OAuth App"
> 3. Fill in:
>    - **Application name**: `Open Source Contribution Atelier`
>    - **Homepage URL**: `http://localhost:8000`
>    - **Authorization callback URL**: `http://localhost:8000/accounts/github/login/callback/`
> 4. Copy `Client ID` and `Client Secret` to `backend/.env`:
>    ```
>    GITHUB_OAUTH_CLIENT_ID=your_client_id
>    GITHUB_OAUTH_CLIENT_SECRET=your_client_secret
>    ```

### 2. Run the Backend (Django)
Ensure you are using **Python 3.9+**.
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Setup the local SQLite database
python manage.py migrate
python manage.py seed_lessons
python manage.py seed_dashboard

# Start the server
python manage.py runserver
```
- API: `http://localhost:8000/api/`

### 3. Run the Frontend (React + Vite)
Ensure you are using **Node 20+**.
```bash
cd frontend
npm install
npm run dev
```
- SPA: `http://localhost:5173/`

---

## 🐳 Docker (Full Stack)

Spin up the entire stack (Postgres, Redis, Django backend, Celery worker, Vite frontend) with a single command:

```bash
docker compose up --build
```

This boots:

| Service | URL | Description |
|---|---|---|
| **postgres** | `localhost:5432` | Database |
| **redis** | `localhost:6379` | Celery broker + Channels cache |
| **backend** | `http://localhost:8000/api/` | Django REST API with hot-reload |
| **celery_worker** | — | Background task processor for email notifications |
| **frontend** | `http://localhost:5173/` | Vite dev server with hot-reload |

> [!TIP]
> The Celery worker mounts the codebase as a volume (`./services/notifications_worker:/app`),
> so code changes take effect immediately without rebuilding the image.
> Restart the worker with `docker compose restart celery_worker` after editing `worker.py`.

### Environment Variables

The Docker backend reads these environment variables automatically. You can override them in `docker-compose.yml` or via a `.env` file:

```bash
cp backend/.env.example backend/.env
```

Key variables for Docker:

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `postgres://atelier:atelier@postgres:5432/atelier` | Auto-configured |
| `REDIS_URL` | `redis://redis:6379/0` | Auto-configured |
| `DEBUG` | `True` | Development mode |

---

## ☁️ Deployment (Vercel)

This project is fully configured to be deployed on **Vercel** as a monorepo.
1. Import the repository into your Vercel dashboard.
2. Vercel will automatically detect the configuration in `vercel.json` and deploy both the Vite frontend and the Django backend as a serverless API.
3. Ensure you add all backend environment variables (from `backend/.env.example`) into your Vercel project settings.

---

## 🧑‍💻 Contributing

We welcome contributions of all levels suitable for **SSoC 2026** and long-term participation!

> [!IMPORTANT]
> **Before requesting an issue**, please read the pinned guide issues on the [Issues tab](https://github.com/nandinigoyaldev/Open-Source-Contribution-Atelier/issues) to understand the keyword assignment rules, CI checks, and the 3-day stale policy.

### Quick Links
| Resource | Description |
|---|---|
| 📋 [CONTRIBUTING.md](.github/CONTRIBUTING.md) | Forking, branching guidelines, commit conventions, and review cycles |
| 💬 [CODE_OF_CONDUCT.md](.github/CODE_OF_CONDUCT.md) | Community participation guidelines |
| 🔒 [SECURITY.md](.github/SECURITY.md) | Responsible vulnerability disclosure policy |
| 📖 [Content Guide](docs/CONTENT_GUIDE.md) | How to add lessons, modules, and quizzes (zero code changes!) |

---

## 🤝 Contributors

Thanks to all the amazing people who have contributed to this project! 💜

<a href="https://github.com/nandinigoyaldev/Open-Source-Contribution-Atelier/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=nandinigoyaldev/Open-Source-Contribution-Atelier&max=100&columns=12" />
</a>

<br/>

> Want to see your avatar here? Check the [Contributing Guide](.github/CONTRIBUTING.md) and pick an issue to get started!

---

<div align="center">

### 💖 Support the Project

If you find this project helpful, please consider giving it a ⭐ star on GitHub!

[![Star this repo](https://img.shields.io/badge/⭐_Star_this_Repo-FFD700?style=for-the-badge&logo=github&logoColor=black)](https://github.com/nandinigoyaldev/Open-Source-Contribution-Atelier)
[![Fork this repo](https://img.shields.io/badge/🍴_Fork_this_Repo-45B7D1?style=for-the-badge&logo=github&logoColor=white)](https://github.com/nandinigoyaldev/Open-Source-Contribution-Atelier/fork)
[![Sponsor](https://img.shields.io/badge/💖_Sponsor-EA4AAA?style=for-the-badge&logo=githubsponsors&logoColor=white)](https://github.com/sponsors/nandinigoyaldev)

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:FF6B6B,50:4ECDC4,100:45B7D1&height=100&section=footer" width="100%" />

</div>
