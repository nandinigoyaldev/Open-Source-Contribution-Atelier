# Dashboard Query-Count Budget

## 1. Overview and Problem

Dashboard endpoints (`/api/dashboard/contributor/`, `/api/dashboard/admin/`, `/api/dashboard/stats-public/`) aggregate metrics from across multiple domains: user profiles, streak profiles, lesson progress, exercise attempts, earned badges, issue tracking, and pull requests.

Without automated query-count budgets, endpoints can easily acquire **N+1 queries** that go unnoticed in development:
- Iterating over pull requests or issues and accessing related objects (e.g., `pr.user` or `pr.issue`) without `select_related` executes an extra query per item ($O(N)$).
- Iterating over lessons or progress entries without `prefetch_related` or `select_related` introduces linear query growth ($O(N)$).
- Aggregating metrics across multiple organizations or learners without subqueries or database aggregates can cause queries to scale with tenant or user counts.

To eliminate this class of regression, the dashboard test suite (`backend/apps/dashboard/tests/test_dashboard_performance.py`) enforces strict, justified query-count ceilings.

---

## 2. Query Budgets and Justifications

The budget is defined in `DASHBOARD_QUERY_BUDGETS` within `backend/apps/dashboard/tests/test_dashboard_performance.py`:

| Key | Endpoint | Max Queries | Justification & Query Breakdown |
| --- | --- | :---: | --- |
| `contributor_dashboard_full` | `/api/dashboard/contributor/` | **28** | **Cold full contributor request (all 7 default fields)**:<br>• **21 application queries**:<br>  - `CustomerSubscription` check (`RateLimitMiddleware`) (1 query)<br>  - `personal_stats` (8 queries): Solved issues count, merged PRs count, completed lesson XP `Sum`, solved issues points `Sum`, challenge bonus XP `Sum`, `StreakProfile` fetch, rank `Subquery` on `User`, earned `UserBadge` slugs.<br>  - `assigned_issues` (1 query): Active assigned issues filter.<br>  - `recent_prs` (1 query): Recent pull requests with `select_related('issue')`.<br>  - `progress_tracker` (2 queries): User completed lesson count and total curriculum lesson count.<br>  - `active_track` (5 queries): Active season, user milestone completions, milestone count, next milestone, and milestone progress count.<br>  - `continue_learning` (1 query): Incomplete lesson progress with `select_related('lesson')`.<br>  - `weekly_goal` (1 query): `WeeklyGoal.get_or_create_current(user)`.<br>• **Framework overhead (5 queries)**: `SessionMiddleware` / `LocaleMiddleware` session persistence (`django_session` lookup, savepoint, insert, table info, release savepoint). |
| `contributor_dashboard_personal_stats` | `/api/dashboard/contributor/?fields=personal_stats` | **16** | **Cold personal stats sub-request**:<br>• 9 application queries (`CustomerSubscription`, 5 completion and XP aggregates, `StreakProfile` fetch, correlated subquery leaderboard rank calculation, earned `UserBadge` slugs).<br>• Framework session-persistence overhead. |
| `admin_dashboard` | `/api/dashboard/admin/` | **18** | **Cold admin dashboard overview**:<br>• Auth and role verification (`Admin` RBAC role).<br>• System-wide issue counts (total, solved, open, in-progress).<br>• System-wide pull request counts (total, merged, open, closed).<br>• Distinct active contributors count.<br>• Pending PRs queue with `select_related('user', 'issue')` ensuring constant $O(1)$ query count regardless of queue length.<br>• Framework session overhead. |
| `public_landing_stats` | `/api/dashboard/stats-public/` | **10** | **Cold public landing stats**:<br>• 3 application queries (unauthenticated non-staff user count, completed lessons count, and total lesson XP delta aggregate).<br>• 5 framework session-persistence queries (`SessionMiddleware` / `LocaleMiddleware`). |

---

## 3. Test Dataset Architecture

The test suite runs against an isolated, synthetic dataset (`multi_org_dashboard_dataset`) built inside the test transaction:
- **Multiple Organizations**: Includes distinct organizations (`Alpha Labs`, `Beta Institute`, `Gamma Academy`) to verify cross-tenant data isolation and ensure tenant scoping does not introduce per-tenant queries.
- **Multiple Learners**: Includes multiple learners in each organization with diverse states (completed vs incomplete lessons, earned badges, streaks, weekly goals, solved vs open issues, merged vs open pull requests).
- **Independent of Production**: The test database is completely synthetic and isolated (`@pytest.mark.django_db`); it does not read from or depend on any production or seeded database state.
- **$O(1)$ Scalability Test**: `test_dashboard_query_count_scales_o1_with_learners_and_organizations` explicitly measures query counts with a baseline dataset, doubles the number of learners and organizations, and asserts that queries executed remain **100% identical**.

---

## 4. Failure Reporting: Identifying Endpoint and Query Count

When an endpoint exceeds its query budget, the test assertion fails with an explicit message that identifies:
1. The exact **endpoint URL** and query parameters.
2. The **actual query count** executed.
3. The **budget limit** allowed.
4. A full formatted log of every **captured SQL query** and its execution duration.

### Example Failure Output

```
AssertionError: Query budget exceeded for endpoint '/api/dashboard/contributor/'!
Executed: 28 queries
Budget:   25 queries (3 queries over budget)
Captured queries:
  [1] (0.001s): SELECT "accounts_user"."id", ... FROM "accounts_user" WHERE ...
  [2] (0.000s): SELECT "accounts_userprofile"."id", ... FROM "accounts_userprofile" WHERE ...
  ...
  [26] (0.001s): SELECT "content_lesson"."id", "content_lesson"."slug", ... FROM "content_lesson" WHERE ...
  [27] (0.001s): SELECT "content_lesson"."id", "content_lesson"."slug", ... FROM "content_lesson" WHERE ...
  [28] (0.001s): SELECT "content_lesson"."id", "content_lesson"."slug", ... FROM "content_lesson" WHERE ...
```

---

## 5. How to Intentionally Update Query Budgets

When adding a new feature or modifying an endpoint that genuinely requires additional database queries:

### Step 1: Confirm the Query Increase is Not an N+1 Regression
- Ensure related models are fetched using `select_related` (for `ForeignKey` / `OneToOne`) or `prefetch_related` (for `ManyToManyField` / reverse `ForeignKey`).
- Ensure metrics across sets of records use database aggregates (`Sum`, `Count`) or `Subquery` rather than Python-level loops.
- Run `test_dashboard_query_count_scales_o1_with_learners_and_organizations` to confirm the queries remain constant when data volume scales.

### Step 2: Measure the New Query Baseline
Run the test in verbose mode to observe the exact queries:
```bash
cd backend
pytest apps/dashboard/tests/test_dashboard_performance.py -k "test_contributor_dashboard_full_request_query_budget" -s
```

### Step 3: Update `DASHBOARD_QUERY_BUDGETS`
Open `backend/apps/dashboard/tests/test_dashboard_performance.py` and update the relevant entry in `DASHBOARD_QUERY_BUDGETS`:
1. Adjust `max_queries` to the new stable ceiling (allow a tight margin for framework overhead).
2. Update the `reason` field with an itemized explanation of the new query and why it is necessary.

### Step 4: Update Documentation
Update Section 2 ("Query Budgets and Justifications") of this document (`docs/backend/DASHBOARD_QUERY_BUDGET.md`) with the new query count and justification.

### Step 5: Verify the Test Suite
Run the full dashboard performance test suite:
```bash
cd backend
pytest apps/dashboard/tests/test_dashboard_performance.py
```
Ensure all budget tests and the $O(1)$ scalability test pass.
