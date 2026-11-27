# Rate limit headers

Every API response that went through a rate limit says how much of that limit is left. Clients can use it to slow down before they get a `429`.

| Header | Value |
| :--- | :--- |
| `X-RateLimit-Limit` | Requests allowed in the window of the limit being reported |
| `X-RateLimit-Remaining` | Requests left in that window (`0` on a `429`) |
| `X-RateLimit-Reset` | Unix time in seconds at which that limit next frees capacity |
| `Retry-After` | Only on `429`: whole seconds to wait before trying again |

```
HTTP/1.1 200 OK
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 41
X-RateLimit-Reset: 1790000040
```

```
HTTP/1.1 429 Too Many Requests
Retry-After: 23
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1790000063

{"error": "rate_limited", "code": "rate_limited", "message": "...", "retry_after": 23}
```

The status codes and bodies of responses are the same as without the headers.

## Which limit is reported

A request can be counted against more than one limit at once: the hourly budget for your tier, the per-minute budget for the kind of endpoint, and any throttle on the view itself (login, AI tutor, events, ...). The three headers describe **the most restrictive one**, which is the one with the fewest requests left. If two have the same number left, the one that resets later is reported, so waiting until `X-RateLimit-Reset` is always enough.

On a `429` the reported limit is the one that refused the request.

The values come from the configured rates (`REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]`, `API_RATE_LIMIT_*` and `RATE_LIMIT_*` settings), so they follow whatever is set for the deployment. The defaults:

| Limit | Default |
| :--- | :--- |
| Anonymous, per IP | 100/hour |
| Authenticated, per user | 1000/hour |
| Premium, per user | 10000/hour |
| Reads (`GET`, `HEAD`, `OPTIONS`) | 60/minute (x5 for premium) |
| Writes (`POST`, `PUT`, `PATCH`, `DELETE`) | 20/minute (x5 for premium) |
| Auth endpoints | 5/minute |

Individual endpoints can have their own, usually lower, limit (for example `auth_login` 5/minute, `ai_tutor` 10/minute, `events_list` 60/minute).

The older `X-RateLimit-Category`, `X-RateLimit-Category-Limit` and `X-RateLimit-Category-Remaining` headers are still sent on requests that went through the endpoint category limit.

## Notes

- `X-RateLimit-Reset` is an absolute time, `Retry-After` is a number of seconds. Both are rounded up to whole seconds.
- Windows are rolling for view throttles and fixed for the tier and category budgets, so `Reset` is the time the oldest counted request ages out (or the window ends), not a promise that the limit is back to full.
- A `429` raised without a throttle behind it has `Retry-After` and `X-RateLimit-Remaining: 0` but no `X-RateLimit-Limit`.
- Throttles keyed on a value the caller picks (the username on login, the email on password reset) are not counted in the headers of successful responses.
- Browsers can read these headers from the frontend origin because they are listed in `CORS_EXPOSE_HEADERS`.
- Endpoints that are not rate limited (health checks, static files, webhooks) send no rate limit headers.

## AI tutor daily token budget

On top of the request limits above, `POST /api/ai/tutor/ask/` has a daily budget of LLM tokens (prompt plus completion) per user. It is checked before the request reaches any LLM provider and resets at 00:00 UTC. Hints and evaluations (`action: "hint"` / `"evaluate"`) are rule based and do not use it.

| Who | Tokens per UTC day |
| :--- | :--- |
| Free learners | `AI_TUTOR_FREE_DAILY_TOKENS` (10,000) |
| Premium (active subscription, staff, or a premium tier) | `AI_TUTOR_PREMIUM_DAILY_TOKENS` (50,000) |
| User with an `AITokenBudgetOverride` (admin) | the override's limit, `0` blocks the user |
| Member of an organization with an active `AITokenOrganizationPool` (admin) | the pool's limit, shared by all members |

An override wins over a pool, and a pool wins over the tier.

| Header | Value |
| :--- | :--- |
| `X-AI-Token-Budget-Limit` | Tokens allowed today |
| `X-AI-Token-Budget-Remaining` | Tokens left when the request was let in |
| `X-AI-Token-Budget-Reset` | Unix time of the next 00:00 UTC |
| `X-AI-Token-Budget-Scope` | `user`, or `organization` for a shared pool |
| `X-AI-Token-Budget-Warning` | Only from `AI_TUTOR_TOKEN_WARNING_PERCENT` (90%) of the budget on |

Once the budget is used up the endpoint returns `429` with `Retry-After` (seconds until midnight UTC):

```
HTTP/1.1 429 Too Many Requests
Retry-After: 3600
X-AI-Token-Budget-Limit: 10000
X-AI-Token-Budget-Remaining: 0

{"error": "ai_token_budget_exhausted", "code": "ai_token_budget_exhausted", "message": "...",
 "limit": 10000, "used": 10000, "remaining": 0, "tier": "free", "scope": "user",
 "reset_at": "2026-03-11T00:00:00Z", "retry_after": 3600}
```

Usage comes from what the provider reports (OpenAI `usage`, also on streams; Anthropic `usage`; Gemini `usageMetadata`). When a provider reports nothing, both sides are estimated at 4 characters per token. A request that is let in with budget left is answered in full, so the last request of the day can go over the limit by up to one answer.

With Redis, counters live in the cache and the Django-Q schedule `flush-ai-token-usage` copies them into `AITokenUsageLedger` every minute. The check reads both, so it does not wait for the flush. Without Redis the cache is a per-process LocMemCache that the flush worker cannot see, so each request writes its tokens straight to the ledger instead (`AI_TUTOR_TOKEN_LEDGER_WRITE_THROUGH`, default `None` = only for LocMemCache).
