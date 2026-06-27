# Contributing to Open Source Contribution Atelier

Thank you for your interest in contributing! We welcome all contributions, from documentation fixes to major feature enhancements. To make the contribution process smooth and successful, please follow these guidelines.

---

## 🛠️ Local Development Setup

To get started quickly, we provide a `Makefile` that wraps the core commands. 

1. **Install Dependencies**:
   ```bash
   make install
   ```
2. **Start the Development Servers (via Docker)**:
   This boots Postgres, Redis, the Django backend, and the Vite frontend:
   ```bash
   make start
   ```
3. **Run Linting & Formatting**:
   Ensure your changes are formatted properly before committing. Pre-commit hooks are configured, but you can also run:
   ```bash
   make format
   ```
4. **Run Unit Tests**:
   ```bash
   make test
   ```

---

## 📋 Pull Request Requirements

We maintain strict quality controls on pull requests to ensure our tests remain green and contributions align with the project goals.

### 1. Linking an Issue
All pull requests must resolve a corresponding open issue. Please reference the issue in your PR description using one of the closing keywords (e.g. `Closes #123` or `Fixes #123`).

### 2. Matching Scope Verification
To prevent partial implementations, the files modified in your pull request must correspond to the scope promised in the linked issue:
- If the issue description mentions **backend** tasks, the PR must modify files in the `backend/` directory.
- If the issue description mentions **frontend** or **ui** tasks, the PR must modify files in the `frontend/` directory.
- If the issue description mentions **database** or **migrations**, the PR must include backend database models or migrations.

**Partial Scope Exemption**: If you are only implementing a specific part of a multi-part issue (e.g., you only know frontend and want to implement the UI layout first), you can easily override the scope verification check by explicitly writing one of the following phrases in your pull request description:
* `Frontend only` / `only frontend`
* `Backend only` / `only backend`
* `Database only`

### 3. SSoC26 Contributors
If you are participating in SSoC26, please check the contributor checkmark `- [x] I am a SSoC26 contributor` in the issue/PR templates. The automation will sync the `SSoC26` label to both your PR and linked issue, and automatically assign them to you.
