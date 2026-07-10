# Contributing Guide

Thank you for considering contributing to **Open Source Contribution Atelier**! This guide explains how to get started, the workflow we follow, and best practices.

## Getting Started
1. **Fork the repository** – click the **Fork** button on GitHub.
2. **Clone your fork**:
   ```bash
   git clone https://github.com/<your‑username>/Open-Source-Contribution-Atelier.git
   cd Open-Source-Contribution-Atelier
   ```
3. **Create a new branch** for your work:
   ```bash
   git checkout -b <type>/<short‑description>
   # e.g. feat/add‑new‑module or bug/fix‑login‑error
   ```
4. **Install dependencies** – see the `README` for backend/frontend setup.
5. **Run the verification checklist** to ensure everything passes:
   ```bash
   ./verify.sh
   ```
   *(This runs frontend linting, formatting check, and tests, followed by backend formatting check and django tests. Alternatively, you can run them manually inside `backend` and `frontend` directories).*

## Commit Messages
We follow the **Conventional Commits** format:
```
<type>(optional scope): <description>

[optional body]
[optional footers]
```
Examples:
- `feat(auth): add Google OAuth login`
- `fix(ui): correct typo in button label`
- `docs(readme): update badge URLs`

## Opening Issues & PRs
- Use the appropriate **issue template** (Bug, Feature, Documentation, Question) – the chooser is configured in `.github/ISSUE_TEMPLATE/config.yml`.
- Reference the related issue in your PR description using `#<issue‑number>`.
- Ensure your PR passes **CI** and **Dependabot** checks before merging.

## Review Process
- PRs are automatically labeled and assigned by our GitHub Actions (welcome bot, label sync, etc.).
- A maintainer will review your changes, suggest improvements, and approve the merge.
- Once approved, the PR will be merged and the release drafter will include it in the next draft release.

## Code Style & Linting
- Backend: `black` and `isort` (run `black . && isort .`).
- Frontend: Prettier and ESLint (run `npm run format` and `npm run lint`).

## Thank You!
Your contributions help make this project better for everyone. If you have any questions, feel free to open a **Question** issue or join the discussion on GitHub Discussions.
