# Repository Audit Report: Open Source Contribution Atelier

This report evaluates the current codebase state, architectures, and quality metrics of the **Open Source Contribution Atelier** project as of June 2026. The findings herein inform the preparations for **SSOC 2026** and long-term community contributions.

---

## 🏗️ 1. Architecture
- **Backend Architecture**: Built on Django 4.2 LTS and Django REST Framework (DRF). Utilizes Django Channels for WebSockets and async operations. SQLite is configured as the local database, while PostgreSQL is intended for production environments. Caching is handled through Redis, with a socket-check fallback to `LocMemCache`.
- **Frontend Architecture**: Structured as a Single Page Application (SPA) using React 19, TypeScript, and Vite. Handles state management via React hooks and caching using TanStack React Query (`@tanstack/react-query`). Uses Recharts for analytics and Re-brutalist styling patterns.
- **Git Sandbox Verification Engine**: Found in `apps.sandbox.linter` and `apps.sandbox.services`. A rule-based parser verifies Git syntax safety by checking command prefixes against an allowlist (`git init`, `git commit`, `git add`, etc.) and using `difflib` to return educational typo correction hints.

---

## 🧹 2. Code Quality
- **TypeScript & Typing Consistency**: The code utilizes modern TypeScript patterns, but compilation is currently broken due to:
  - Missing Lucide React import (`X` is used on line 743 of `DashboardPage.tsx` but not imported).
  - Missing typing properties (`Lesson` interface in `lessons.ts` does not contain `points?: number`, which is accessed across `LessonPage.tsx`).
  - Missing global test environment typings (`global.fetch` in `Dashboard.test.tsx` fails TypeScript type-checking).
- **Python Code Quality**: Clean modular structure using Django Apps. Type hints are PEP 484-compliant, updated for compatibility with Python 3.9+ environments.

---

## 💸 3. Technical Debt
- **Unused Notification System**: `apps.notifications` has Django Channels Consumers and WebSocket routers, but the frontend code does not implement any WebSocket connection or notification interface. The notification system remains dead/incomplete code.
- **Code Duplication**: Local curriculum lists are stored both in `frontend/public/content/curriculum.json` and in backend models, requiring dual updates.
- **CI/CD Constraints**: No lint rules (`ruff` / `flake8` / `eslint`) are automatically verified or blocked in git pre-commit hooks or GitHub action workflows.

---

## 📖 4. Documentation
- **Core Files**: Core community onboarding documentation exists (`README.md`, `CONTRIBUTING.md`, `SUPPORT.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`).
- **Internal Guidelines**: The content guides (`CONTENT_GUIDE.md`) are excellent, but developer setup instructions lacked detailed virtualenv parameters for Python 3.9 setups.
- **Architectural & Maintainer Documentation**: `infra/architecture.md` and `infra/maintainer-playbook.md` are barebones and need significant expansion to help onboarding triage maintainers.

---

## 🧑‍💻 5. Contributor Experience
- **Local Onboarding**: The fallback to SQLite database and `LocMemCache` makes the local onboarding experience fast (zero-dependency).
- **Typo Tolerant Linter**: The interactive terminal features real-time syntax checking, making it highly forgiving for beginners learning git syntax.
- **Issues Repository**: Replicating development tasks in `.github/issues` and `docs/issues/` with difficulty labels (`easy`, `medium`, `hard`) makes picking up tickets clear and straightforward.

---

## ♿ 6. Accessibility (a11y)
- **Contrast & Visual Structure**: High contrast neobrutalist elements provide clean visual separation.
- **Missing Speech Labels**: Several interactive cards and light/dark theme switchers lack standard `aria-label` or `aria-live` speech wrappers, making them inaccessible to screen readers.
- **Keyboard Navigation**: Form submissions are mouse-dependent; interactive terminals should support standard keyboard combinations like `Cmd+Enter` / `Ctrl+Enter` to run tests.

---

## 🎨 7. UI/UX
- **Theme**: Premium neobrutalist design with stark borders, high contrast shadows, and bright colors.
- **Responsive Layout**: Clean desktop layout, but lacks mobile navigation drawers for lesson catalogs and dashboard views.
- **Micro-Animations**: Hover animations on cards and active outlines are minimal and can be polished.

---

## 🔑 8. Authentication
- **Token Infrastructure**: Secure token-based authentication with `rest_framework_simplejwt` JWT pairs (Access/Refresh).
- **Google OAuth**: A newly registered OAuth Client ID (`27042928964-pbolsldqvdv2hfipblmrcf332evg83v8.apps.googleusercontent.com`) resolved the `401: invalid_client` login bugs.
- **GitHub OAuth**: The callback page exists on the frontend, but the backend implementation is incomplete.

---

## 🚀 9. Deployment
- **Configuration**: Standard `render.yaml` for Render deployment.
- **Routing**: Single Page Application redirects are set up with `frontend/public/_redirects` to prevent 404 errors on browser reloads.

---

## ⚡ 10. Performance
- **Dashboard Refetches**: The frontend refetches the static curriculum json file on every dashboard page mount, rather than caching it in TanStack React Query or LocalStorage.
- **Database Indexing**: Lack of database indexes on foreign keys in SQLite (e.g. `LessonProgress.user` / `LessonProgress.lesson`) can lead to slower queries as user count grows.

---

## 🧪 11. Testing
- **Test Infrastructure**: Standard testing using `pytest` (backend) and `vitest` (frontend).
- **Coverage**: Includes 35 Django unit tests and 7 Vitest files.
- **Visual Tests**: Lack of regression or visual flow tests (e.g. Playwright or Cypress).

---

## 🔒 12. Security
- **Sandbox Safety**: Git command execution is completely mocked and sandboxed. User inputs are evaluated as strings or regular expressions, preventing remote code execution (RCE) on the server.
- **Secret Hygiene**: Production secrets are loaded exclusively via environment variables. Dummy fallback credentials prevent crashes during local testing.

---

## 📈 13. Scalability
- **Django Channels Redis Dependency**: If the Redis service is unavailable, Django Channels crashes on WebSocket requests. Dynamic fallbacks are needed to keep the system resilient during Redis outages.
