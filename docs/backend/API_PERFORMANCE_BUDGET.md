# API Performance Budget

`backend/perf_budget.json` holds the latency and query limits for a short list
of representative API routes. The `API Performance Budget` workflow
(`.github/workflows/api-performance-budget.yml`) runs
`python manage.py perf_budget_report` on every PR that touches `backend/` and
fails when a route goes over its budget. The frontend has its own budget, see
`docs/frontend/PERFORMANCE_BUDGET.md`.

## Run it locally

```bash
cd backend
python manage.py perf_budget_report
```

It builds a throwaway test database (so your development data is not touched),
migrates it, seeds the dataset below, and prints a Markdown report. Expect
about a minute, most of it spent on migrations. The exit code is non zero when a
route is over budget.

Useful options:

| Option                          | What it does                                                        |
| ------------------------------- | ------------------------------------------------------------------- |
| `--runs N` / `--warmup N`       | timed and warmup requests per route (default 40 and 5)              |
| `--output report.md`            | also write the Markdown report to a file                            |
| `--json-output report.json`     | write the raw measurements (the CI job uploads this)                |
| `--budget path.json`            | use another budget file                                             |
| `--update-budget --reason "..."`| raise the budgets that are exceeded, see below                      |
| `--from-report report.json`     | use saved measurements instead of measuring (for `--update-budget`) |
| `--current-db`                  | seed into the configured database instead of a throwaway one        |

## What is measured

The dataset is fixed: 50 users, 60 lessons, 150 completed lesson progress rows
and 250 XP events. Everything is derived from the loop index (no `random`, no
dates), so every run has the same rows. It is built in
`backend/apps/core/perf_budget_runner.py`. The older `seed_perf_data` command
is not used here: it picks random values, writes 500k rows and still creates
`XPEvent` rows with fields the model no longer has.

The routes (`ROUTES` in the same file) are called through the Django test client
as an authenticated user:

| Name              | Path                                      |
| ----------------- | ----------------------------------------- |
| `health-legacy`   | `/health/legacy/`                         |
| `lessons-list`    | `/api/content/published-lessons/`         |
| `lesson-detail`   | `/api/content/published-lessons/<id>/`    |
| `leaderboard`     | `/api/leaderboard/`                       |
| `content-search`  | `/api/content/search/?q=lesson`           |
| `learning-paths`  | `/api/content/learning-paths/`            |
| `progress-badges` | `/api/progress/badges/`                   |

To keep the numbers repeatable:

- the requests go round robin (A, B, C, A, B, C ...) so a slow moment on the
  machine is spread over every route
- the cache is cleared before every request, so each sample is the cold path
  (the leaderboard would otherwise just measure the cache)
- the read replica router, the random request sampling in
  `PerformanceTrackingMiddleware` and `DEBUG` query logging are switched off,
  and the cache is a local memory cache (a shared Redis is never touched)
- the garbage collector is paused while a request is timed

For every route the report shows p50, p95 and p99 in milliseconds (nearest rank
percentiles, so each number is a real sample) and the number of SQL queries.
With 40 timed requests, p99 is the slowest one.

## The budget file

```json
{
  "version": 1,
  "margin_pct": 25,
  "routes": {
    "leaderboard": {
      "p95_ms": 60,
      "max_queries": 7,
      "reason": "Why this number is what it is."
    }
  }
}
```

| Field                      | Meaning                                                                    |
| -------------------------- | -------------------------------------------------------------------------- |
| `version`                  | schema version, currently `1`                                              |
| `margin_pct`               | how far above `p95_ms` a route may go before the job fails                 |
| `routes.<name>.p95_ms`     | latency budget for the p95, in milliseconds                                |
| `routes.<name>.max_queries`| most SQL queries one request may run                                       |
| `routes.<name>.reason`     | required, a sentence about why the budget has this value                   |

A file that breaks this schema (missing reason, negative number, ...) is
rejected with a message that names the field.

## How the result is decided

| Status        | When                                                                  | Fails the job |
| ------------- | --------------------------------------------------------------------- | ------------- |
| `ok`          | p95 and query count are within budget                                 | no            |
| `REVIEW`      | p95 is over `p95_ms` but inside `margin_pct`                          | no            |
| `OVER BUDGET` | p95 is more than `margin_pct` over `p95_ms`, or queries > `max_queries` | yes         |
| `NO BUDGET`   | the route is measured but has no entry in the file                    | yes           |
| `ERROR`       | the route did not answer HTTP 200                                     | yes           |
| `STALE`       | the file has an entry for a route that is no longer measured          | no            |

Latency on a shared CI runner is noisy, so a small overshoot is only a
`REVIEW` row (re-run the job, and treat it as real if it stays). The query
count is exact on a fixed dataset, so it has no margin: one extra query fails.

The report lists the worst rows first and has a "What to do" section with one
concrete sentence per problem. It has no timestamp, so the same numbers always
give the same text. The CI job puts it in the job summary and uploads
`api-perf-report.md` and `api-perf-report.json` as an artifact.

## Raising a budget on purpose

A budget goes up only in the same PR as the change that needs it, with a reason
the reviewer can read.

1. Run `python manage.py perf_budget_report` and confirm the route really is
   slower (or runs more queries) because of your change, and that the change is
   worth it.
2. Raise the budget:

   ```bash
   python manage.py perf_budget_report --update-budget \
     --reason "leaderboard joins the profile table so it can show avatars"
   ```

   This sets `p95_ms` to the measured p95 plus 20% (`--headroom-pct`) for routes
   that were over, `max_queries` to the measured count, writes
   `backend/perf_budget.json`, and stores your reason on the changed entries.
   `--reason` is required. It never lowers a budget and never touches routes
   that are within budget.
3. If your machine is much faster or slower than CI, download `api-perf-report.json`
   from the failed job and run
   `python manage.py perf_budget_report --update-budget --reason "..." --from-report api-perf-report.json`
   to use the CI numbers.
4. Commit `backend/perf_budget.json` with the code change and explain the
   increase in the PR description. Reviewers should look at the `reason` line in
   the diff.

To add a route, add a `Route(...)` to `ROUTES` in `perf_budget_runner.py` and
run `--update-budget --reason "..."` once; a new route gets both numbers from
the measurement. To lower a budget after an optimization, edit the JSON by hand
and update the `reason`. To drop a route, remove it from `ROUTES` and from the
file.

## Current numbers

The first budgets were set from runs on a development machine (sqlite) at about
3.5 times the local p95, because shared CI runners are slower and noisier. They
have not been checked on GitHub Actions yet. After the first runs in CI, tighten
them with `--from-report` or by hand so the margin means something.
