# Open Source Contribution Atelier

![Status](https://img.shields.io/badge/status-active-brightgreen?style=for-the-badge) ![License](https://img.shields.io/github/license/goyaljiiiiii/Open-Source-Contribution-Atelier?style=for-the-badge) ![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB) ![Django](https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white) ![TypeScript](https://img.shields.io/badge/TypeScript-007ACC?style=for-the-badge&logo=typescript&logoColor=white) ![Docker](https://img.shields.io/badge/Docker-2CA5E0?style=for-the-badge&logo=docker&logoColor=white) [![Live Demo](https://img.shields.io/badge/Live%20Demo-Visit-blue?style=for-the-badge)](https://contribution-atelier-frontend.onrender.com/)

Welcome to the **Open Source Contribution Atelier** — a complete Open Source Learning Platform designed to help a beginner confidently transition from *"I know nothing about Open Source"* to *"I can confidently contribute to real open source repositories."*

The platform preserves a playful, neobrutalist developer console aesthetic while delivering a structured, gamified curriculum.

---

## Technical Stack

- **Frontend**: React 19, TypeScript, Vite, Tailwind CSS (Neobrutalist Theme), React Router 7, TanStack React Query
- **Backend**: Django, Django REST Framework, Simple JWT, PostgreSQL, Redis (Caching)
- **Deployment**: Configured for monorepo environments (e.g. Netlify for static frontend, Render/Docker for backend)

---

## Key Features

1. **Structured Learning Curriculum**: 8 core modules going from mindset basics to advanced conflict resolution.
2. **Markdown-Driven Content**: Lessons and metadata are parsed dynamically. Adding content requires no code changes. See the [Content Guide](CONTENT_GUIDE.md).
3. **Interactive Quizzes**: Theoretical modules feature multiple-choice checking dashboards.
4. **Sandbox Terminal**: Practical Git lessons incorporate a mock-up sandbox terminal that validates inputs.
5. **Gamification & Badges Cabinet**: Locked and unlocked milestone rewards mapping directly to module progress.
6. **Printable Completion Certificates**: Generates a gorgeous A4 neobrutalist certificate with verification hashes once the curriculum hits 100%.
7. **Hall of Fame & Leaderboard**: Cohort stats, active streak calendars, and GitHub contributor APIs recognition boards.
8. **Onboarding Guide Tour**: Walkthrough sliders introduce the sandbox console to newcomers.

---

## Learning Curriculum Overview

- **Module 1: Introduction to Open Source**: Mindset, Why it matters, History, and Misconceptions.
- **Module 2: Git Fundamentals**: Repos, Commits, Branching, Merging, and Remotes.
- **Module 3: GitHub Fundamentals**: Forks, Pull Requests, Issues, Discussions, and Organizations.
- **Module 4: Open Source Etiquette**: Respectful communication, Reading README & CONTRIBUTING files first, and Review processes.
- **Module 5: First Contribution**: Interactive step-by-step mock PR setup drill.
- **Module 6: Real Contribution Workflow**: Tracing Issue -> Assignment -> Develop -> PR -> Review -> Merge cycles.
- **Module 7: Advanced Open Source**: Rebasing, Squashing, Conflict resolution, and CI/CD checks.
- **Module 8: Finding Projects**: Discovering issues using filters, Hacktoberfest, and good first issues.

---

## Directory Structure

```text
├── backend/            # Django REST API, views, tests, and caching logic
├── frontend/           # React SPA frontend UI
│   ├── public/         
│   │   ├── content/    # Static Markdown files and curriculum.json metadata catalog
│   │   └── _redirects  # Netlify single page application redirect configuration
│   └── src/            # Components, pages, hooks, state
├── netlify.toml        # Root Netlify configuration mapping monorepo builds
└── CONTENT_GUIDE.md    # Playbook on how to write/add lessons, modules, and quizzes
```

---

## Quick Start

### Docker Setup
To boot both the Django backend and React frontend:
```bash
docker compose up --build
```
- Backend REST API: `http://localhost:8000/api/`
- Frontend SPA: `http://localhost:5173/`

### Manual Development Setup

Follow these steps to run the client and server locally on your system.

#### 1. Setup Environment Files
```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

#### 2. Initialize Backend
The Django backend supports **Python 3.9+** and defaults to a local SQLite database for effortless onboarding without needing PostgreSQL or Redis.
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_lessons
python manage.py seed_dashboard
python manage.py runserver
```
- Backend REST API: `http://localhost:8000/api/`
- Interactive API Docs: `http://localhost:8000/api/docs/`

#### 3. Run Frontend
The frontend uses Vite and React. Ensure you are using **Node 20+**. We recommend using **NVM** to manage Node versions.
```bash
cd frontend
# If using NVM, load it and switch to Node 20
source ~/.nvm/nvm.sh && nvm use 20
npm install
npm run dev
```
- Frontend SPA: `http://localhost:5173/`

---

## 🧪 Testing

Run tests locally to prevent regressions:
- **Backend tests**: `cd backend && pytest`
- **Frontend tests**: `cd frontend && npm run test`

---

## 🧑‍💻 Contributing & Community Guides

We welcome contributions of all levels suitable for **SSOC 2026** and long-term participation! Please review our guides:
- **[CONTRIBUTING.md](CONTRIBUTING.md)**: Forking, branching guidelines, commit conventions, and review cycles.
- **[SUPPORT.md](SUPPORT.md)**: How to get help, community channels, and asking questions.
- **[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)**: Community participation guidelines.
- **[SECURITY.md](SECURITY.md)**: Responsible vulnerability disclosure rules.
- **[CONTENT_GUIDE.md](CONTENT_GUIDE.md)**: Write new modules, markdown lessons, or interactive quizzes without modifying code.
