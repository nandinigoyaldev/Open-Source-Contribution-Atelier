# Release Checklist

For maintainers shipping a change to production. Copy the sections that apply into the pull request or release notes and tick them off. Every command names something that already exists in this repository.

**Where things run:** the frontend is built and deployed on Vercel (`frontend/vercel.json`); the backend runs from `backend/` (Render blueprint in `infra/deploy/render.yaml`, Docker image from `backend/Dockerfile`, Hugging Face for the hosted instance). A deploy of the backend runs `python manage.py migrate` on start.

## 1. Which sections do I need?

| The change touches | Do sections |
| --- | --- |
| Only `frontend/` (and docs) | 2, 5 (frontend rows), 6 (frontend) |
| Only `backend/` (and docs) | 3, 4, 5 (backend rows), 6 (backend) |
| Both, or `docker-compose*.yml`, `Dockerfile`, `infra/` | 2, 3, 4, 5, 6 (full stack) |
| Only docs / CI | Nothing here; check the CI result |

**Order for a full-stack release:** backend first (migrations are additive and the old frontend keeps working), then the frontend. A change that removes or renames an API field or an environment variable needs two releases: add the new one, release, switch the other side, release, then remove the old one.

## 2. Frontend

- [ ] `cd frontend && npm ci` then `npm run lint` and `npm run type-check` pass
- [ ] `npx vitest run --project unit` passes (the same tests as the "Frontend Unit Tests" job)
- [ ] `npm run build` completes with 0 errors (build output goes to `frontend/dist`; it runs the client and SSR builds and `prerender.js`)
- [ ] `npm run perf:budget` (or the "performance-budget" workflow) is within the budget in `frontend/performance-budget.json`
- [ ] New or changed `VITE_*` variables are set in Vercel **before** building: they are baked into the bundle at build time, so changing one later needs a new deploy. Names and defaults are in `frontend/.env.example`
- [ ] Changed API types: `cd frontend && npm run generate:api` leaves no uncommitted diff in `src/types/api.d.ts` (the `api-types` workflow checks this)

## 3. Backend code and configuration

- [ ] `cd backend && black --check . && isort --check-only .`, then `pytest` passes
- [ ] `python backend/manage.py check --deploy` has no errors (the "Release Readiness" workflow runs this and the frontend build; trigger it from the Actions tab and type `RELEASE`)
- [ ] `python backend/manage.py check_curriculum_slugs` reports no drift between `curriculum.json` and the lessons in the database, if lessons or curriculum files changed
- [ ] New or changed environment variables are added to `backend/.env.example` **and** set in the hosting dashboard (Render / Hugging Face secrets). Secrets are never committed. Compare with `infra/deploy/render.yaml` and `infra/deploy/docker-compose.prod.yml`
- [ ] Dependencies: `backend/requirements.txt` and `backend/requirements-prod.txt` agree (the "Dependency Drift" check enforces this) and `make scan-vulns` shows nothing new at HIGH

## 4. Migrations

See `docs/MIGRATIONS.md` for the workflow. Before deploying:

- [ ] `python backend/manage.py makemigrations --check --dry-run` reports "No changes detected" (no model change without a migration)
- [ ] `python backend/manage.py showmigrations` lists the new migrations; read the SQL of risky ones with `python backend/manage.py sqlmigrate <app> <number>`
- [ ] The migration is safe while the **old** code is still running: adding a nullable column or table is fine; dropping or renaming a column, or adding a `NOT NULL` column without a default, must be split into two releases
- [ ] Large data migrations are batched and tested on a copy of production-sized data
- [ ] A database backup exists: `cd backend && python scripts/backup_db.py` (needs the S3 settings from `backend/.env.example`) or the hosting provider's snapshot, taken **before** `migrate` runs

## 5. Smoke tests after deploying

Run against the real URLs (staging first when there is one).

| Check | How |
| --- | --- |
| Backend is up and healthy | `curl -fsS https://<backend>/health/` returns 200 |
| API and latency | `python scripts/verify_staging_deployment.py --base-url https://<backend> --timeout 10 --retries 3` |
| Frontend loads | open the site; the browser console has no red errors; the lessons list loads |
| Sign in and out | sign in with a test account, open the dashboard, sign out |
| One lesson | open a lesson, complete it, check the progress summary updates |
| Background work (if `services/notifications_worker` or Celery changed) | the worker container is running (`docker compose ps`) and its log shows it connected to Redis |
| Logs | no new errors in the backend log or Sentry for 10 minutes |

## 6. Rollback

Decide **before** releasing which of these you would use.

- **Frontend (Vercel):** in the Vercel dashboard, open Deployments, pick the last good one and "Promote to Production" (or `vercel rollback`). No rebuild is needed. Remember `VITE_*` values are part of each build.
- **Backend code:** redeploy the previous commit (revert the merge commit on `main`, or redeploy the previous image tag). Because migrations should be additive (section 4), the old code runs against the new schema.
- **Migration that must be undone:** only if it is reversible. `python backend/manage.py migrate <app> <previous migration number>` reverses it; check first that the migration has a reverse operation (`RunPython` needs a `reverse_code`). If not, restore the backup from section 4.
- **Bad environment variable:** restore the previous value in the dashboard and restart; do not redeploy code for a config mistake.
- [ ] After any rollback, rerun the smoke tests in section 5 and open an issue describing what failed.
