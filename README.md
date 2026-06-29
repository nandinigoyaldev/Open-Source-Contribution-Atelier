<div align="center">
  <img src="https://img.shields.io/badge/status-active-brightgreen?style=for-the-badge" alt="Status" />
  <img src="https://img.shields.io/github/license/goyaljiiiiii/Open-Source-Contribution-Atelier?style=for-the-badge" alt="License" />
  <img src="https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB" alt="React" />
  <img src="https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white" alt="Django" />
  <img src="https://img.shields.io/badge/Vercel-000000?style=for-the-badge&logo=vercel&logoColor=white" alt="Vercel" />
</div>

<br />

<div align="center">
  <h1>🚀 Open Source Contribution Atelier</h1>
  <p><i>A complete Open Source Learning Platform designed to help beginners confidently transition from zero to real open-source contributions.</i></p>
</div>

---

## ✨ Features

- **Gamified Curriculum**: 8 core modules going from mindset basics to advanced conflict resolution.
- **Interactive Quizzes**: Multiple-choice testing dashboards.
- **Badges Cabinet**: Earn milestone rewards mapping directly to module progress.
- **Printable Certificates**: Generates a gorgeous A4 neobrutalist certificate with verification hashes.
- **Hall of Fame**: Cohort stats, active streak calendars, and GitHub contributor APIs recognition boards.
- **Markdown-Driven Content**: Lessons are parsed dynamically. Adding content requires no code changes. See the [Content Guide](CONTENT_GUIDE.md).

---

## 🛠️ Technical Stack

- **Frontend**: React 19, TypeScript, Vite, Tailwind CSS (Neobrutalist Theme), React Router 7, TanStack React Query
- **Backend**: Django REST Framework, Simple JWT
- **Deployment**: Configured as a monorepo for seamless **Vercel** deployment (Serverless Backend + Static Frontend).

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

## ☁️ Deployment (Vercel)

This project is fully configured to be deployed on **Vercel** as a monorepo.
1. Import the repository into your Vercel dashboard.
2. Vercel will automatically detect the configuration in `vercel.json` and deploy both the Vite frontend and the Django backend as a serverless API.
3. Ensure you add all backend environment variables (from `backend/.env.example`) into your Vercel project settings.

---

## 🧑‍💻 Contributing

We welcome contributions of all levels suitable for **SSOC 2026** and long-term participation! Please review our guides:
- **[CONTRIBUTING.md](.github/CONTRIBUTING.md)**: Forking, branching guidelines, commit conventions, and review cycles.
- **[SUPPORT.md](.github/SUPPORT.md)**: How to get help, community channels, and asking questions.
- **[CODE_OF_CONDUCT.md](.github/CODE_OF_CONDUCT.md)**: Community participation guidelines.
- **[SECURITY.md](.github/SECURITY.md)**: Responsible vulnerability disclosure rules.
