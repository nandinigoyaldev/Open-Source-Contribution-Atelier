"""
Daily LLM token budget for the AI tutor.

- Each LLM call made for a user adds its input (prompt) and output (completion)
  tokens to two counters in the Django cache. ``cache.incr`` is atomic on Redis and
  on LocMemCache, so parallel requests never lose an update.
- A counter holds the user's whole total for the UTC day, not a delta. The first
  time it is touched (or after the cache lost it) it is seeded from the ledger row,
  so the counter is never behind the ledger.
- ``flush_usage_to_ledger`` copies the counters into ``AITokenUsageLedger`` with
  GREATEST(), so running it twice, or from two workers at once, changes nothing.
- A budget check reads the counter and the ledger and takes the larger one, so it
  does not depend on how long ago the last flush ran.
- With a per-process cache (LocMemCache, the fallback when Redis is down) the flush
  worker and the other workers cannot see a process's counters, so each request
  writes its tokens straight to the ledger instead (see ledger_write_through).

Limits, in this order:
1. an active ``AITokenBudgetOverride`` for the user (set in the admin)
2. an active ``AITokenOrganizationPool`` for the user's organization, shared by
   every member of it
3. the tier: premium users (``apps.core.throttling.is_premium_user``: an active
   subscription, staff, or a premium tier) get AI_TUTOR_PREMIUM_DAILY_TOKENS,
   everybody else AI_TUTOR_FREE_DAILY_TOKENS

Budgets reset at 00:00 UTC.
"""

import logging
import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from datetime import timezone as dt_timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from django.conf import settings
from django.core.cache import cache, caches
from django.core.cache.backends.locmem import LocMemCache
from django.db import models
from django.db.models import F, Value
from django.db.models.functions import Greatest
from django.utils import timezone

from .models import AITokenBudgetOverride, AITokenOrganizationPool, AITokenUsageLedger

logger = logging.getLogger(__name__)

DEFAULT_FREE_DAILY_TOKENS = 10_000
DEFAULT_PREMIUM_DAILY_TOKENS = 50_000
DEFAULT_WARNING_PERCENT = 90

# Counters live for two days, so the flush that runs just after midnight still
# sees the final totals of the day that just ended.
COUNTER_TTL_SECONDS = 2 * 24 * 60 * 60

# Used only when a provider does not report usage. About 4 characters per token
# is the usual rule of thumb for English text.
CHARS_PER_TOKEN = 4

TIER_FREE = "free"
TIER_PREMIUM = "premium"
TIER_OVERRIDE = "override"
TIER_ORGANIZATION = "organization"

SCOPE_USER = "user"
SCOPE_ORGANIZATION = "organization"

# counter kind -> ledger field
_FIELDS = (("input", "input_tokens"), ("output", "output_tokens"))


@dataclass(frozen=True)
class BudgetStatus:
    """Where one user stands against their daily token budget."""

    limit: int
    used: int
    tier: str
    scope: str
    reset_at: datetime
    warning_percent: int = DEFAULT_WARNING_PERCENT

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)

    @property
    def exhausted(self) -> bool:
        return self.used >= self.limit

    @property
    def percent_used(self) -> int:
        if self.limit <= 0:
            return 100
        return min(100, self.used * 100 // self.limit)

    @property
    def warning(self) -> bool:
        """True from warning_percent of the budget on (integer math, no rounding)."""
        return self.used * 100 >= self.limit * self.warning_percent

    def retry_after_seconds(self, now: Optional[datetime] = None) -> int:
        now = now or timezone.now()
        return max(1, math.ceil((self.reset_at - now).total_seconds()))


def _setting_int(name: str, default: int) -> int:
    try:
        return int(getattr(settings, name, default))
    except (TypeError, ValueError):
        return default


def utc_day(now: Optional[datetime] = None) -> date:
    now = now or timezone.now()
    return now.astimezone(dt_timezone.utc).date()


def next_reset(day: date) -> datetime:
    """Midnight UTC at the end of ``day``."""
    return datetime.combine(day + timedelta(days=1), time.min, tzinfo=dt_timezone.utc)


def estimate_tokens(text: str) -> int:
    """
    Rough token count for text a provider gave no usage numbers for:
    len(text) / CHARS_PER_TOKEN, rounded up so a short reply still costs a token.
    """
    if not text:
        return 0
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def counter_key(day: date, user_id: Any, kind: str) -> str:
    return f"ai_tutor:tokens:{day.isoformat()}:{user_id}:{kind}"


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------- recording


def ledger_write_through() -> bool:
    """
    Whether each request writes its tokens straight to the ledger.

    AI_TUTOR_TOKEN_LEDGER_WRITE_THROUGH decides when set. When it is None (default)
    this is on only for a LocMemCache: every process has its own copy of it, so
    counters there are invisible to the flush worker and to the other workers.
    """
    configured = getattr(settings, "AI_TUTOR_TOKEN_LEDGER_WRITE_THROUGH", None)
    if configured is not None:
        return bool(configured)
    return isinstance(caches["default"], LocMemCache)


def record_usage(
    user: Any,
    input_tokens: int,
    output_tokens: int,
    now: Optional[datetime] = None,
) -> None:
    """Add one LLM call's tokens to the user's counters for the current UTC day."""
    user_id = getattr(user, "pk", None)
    if user_id is None:
        return
    amounts = {
        "input_tokens": max(0, _as_int(input_tokens)),
        "output_tokens": max(0, _as_int(output_tokens)),
    }
    if not any(amounts.values()):
        return

    day = utc_day(now)
    if ledger_write_through():
        _add_to_ledger(day, user_id, amounts)
        return

    not_counted = {}
    for kind, field in _FIELDS:
        amount = amounts[field]
        if amount and not _incr_counter(day, user_id, kind, field, amount):
            not_counted[field] = amount
    if not_counted:
        _add_to_ledger(day, user_id, not_counted)


def _incr_counter(day: date, user_id: Any, kind: str, field: str, amount: int) -> bool:
    key = counter_key(day, user_id, kind)
    try:
        try:
            cache.incr(key, amount)
            return True
        except ValueError:
            pass  # not there yet today, or the cache dropped it
        row, _ = AITokenUsageLedger._default_manager.get_or_create(
            user_id=user_id, date=day
        )
        cache.add(key, getattr(row, field), COUNTER_TTL_SECONDS)
        cache.incr(key, amount)
        return True
    except Exception as exc:
        logger.warning(
            "AI token counter %s unavailable, writing to the ledger instead: %s",
            key,
            exc,
        )
        return False


def _add_to_ledger(day: date, user_id: Any, amounts: Dict[str, int]) -> None:
    row, _ = AITokenUsageLedger._default_manager.get_or_create(
        user_id=user_id, date=day
    )
    AITokenUsageLedger._default_manager.filter(pk=row.pk).update(
        updated_at=timezone.now(),
        **{field: F(field) + amount for field, amount in amounts.items() if amount},
    )


# ------------------------------------------------------------------------ reading


def _sum_usage(day: date, rows: Iterable[Tuple[Any, int, int]]) -> int:
    """Rows are (user_id, ledger input, ledger output). Takes max(cache, ledger) per counter."""
    rows = list(rows)
    if not rows:
        return 0
    keys = [
        counter_key(day, user_id, kind) for user_id, _, _ in rows for kind, _ in _FIELDS
    ]
    try:
        cached: Dict[str, Any] = cache.get_many(keys)
    except Exception as exc:
        logger.warning("AI token counters unreadable, using the ledger only: %s", exc)
        cached = {}

    total = 0
    for user_id, ledger_in, ledger_out in rows:
        total += max(ledger_in, _as_int(cached.get(counter_key(day, user_id, "input"))))
        total += max(
            ledger_out, _as_int(cached.get(counter_key(day, user_id, "output")))
        )
    return total


def get_user_usage(user_id: Any, day: date) -> int:
    row = (
        AITokenUsageLedger._default_manager.filter(user_id=user_id, date=day)
        .values_list("input_tokens", "output_tokens")
        .first()
    )
    ledger_in, ledger_out = row or (0, 0)
    return _sum_usage(day, [(user_id, ledger_in, ledger_out)])


def get_organization_usage(organization_id: Any, day: date) -> int:
    # Every user with usage today has a ledger row (it is created when their
    # counter is first seeded), so the rows say which members to read.
    rows = AITokenUsageLedger._default_manager.filter(
        date=day, user__user_profile__organization_id=organization_id
    ).values_list("user_id", "input_tokens", "output_tokens")
    return _sum_usage(day, rows)


def get_budget_status(user: Any, now: Optional[datetime] = None) -> BudgetStatus:
    now = now or timezone.now()
    day = utc_day(now)
    common = {
        "reset_at": next_reset(day),
        "warning_percent": _setting_int(
            "AI_TUTOR_TOKEN_WARNING_PERCENT", DEFAULT_WARNING_PERCENT
        ),
    }

    override = AITokenBudgetOverride._default_manager.filter(user_id=user.pk).first()
    if override is not None and override.is_active(now):
        return BudgetStatus(
            limit=override.daily_token_limit,
            used=get_user_usage(user.pk, day),
            tier=TIER_OVERRIDE,
            scope=SCOPE_USER,
            **common,
        )

    pool = AITokenOrganizationPool._default_manager.filter(
        is_active=True, organization__users__user_id=user.pk
    ).first()
    if pool is not None:
        return BudgetStatus(
            limit=pool.daily_token_limit,
            used=get_organization_usage(pool.organization_id, day),
            tier=TIER_ORGANIZATION,
            scope=SCOPE_ORGANIZATION,
            **common,
        )

    from apps.core.throttling import is_premium_user

    if is_premium_user(user):
        limit = _setting_int(
            "AI_TUTOR_PREMIUM_DAILY_TOKENS", DEFAULT_PREMIUM_DAILY_TOKENS
        )
        tier = TIER_PREMIUM
    else:
        limit = _setting_int("AI_TUTOR_FREE_DAILY_TOKENS", DEFAULT_FREE_DAILY_TOKENS)
        tier = TIER_FREE
    return BudgetStatus(
        limit=limit,
        used=get_user_usage(user.pk, day),
        tier=tier,
        scope=SCOPE_USER,
        **common,
    )


# ----------------------------------------------------------------------- flushing


def flush_usage_to_ledger(now: Optional[datetime] = None, batch_size: int = 500) -> int:
    """
    Copy the cache counters of today and yesterday into the ledger.

    Only ever raises a ledger value (GREATEST), so it is safe to run again, or
    from two workers at the same time. Returns how many rows changed.
    """
    today = utc_day(now)
    days = [today - timedelta(days=1), today]
    changed = 0
    last_pk = 0
    while True:
        batch: List[Tuple[int, Any, date, int, int]] = list(
            AITokenUsageLedger._default_manager.filter(date__in=days, pk__gt=last_pk)
            .order_by("pk")
            .values_list("pk", "user_id", "date", "input_tokens", "output_tokens")[
                :batch_size
            ]
        )
        if not batch:
            return changed
        last_pk = batch[-1][0]

        keys = [
            counter_key(day, user_id, kind)
            for _, user_id, day, _, _ in batch
            for kind, _ in _FIELDS
        ]
        try:
            cached = cache.get_many(keys)
        except Exception as exc:
            logger.warning("AI token counters unreadable, flush skipped: %s", exc)
            return changed

        for pk, user_id, day, ledger_in, ledger_out in batch:
            cached_in = _as_int(cached.get(counter_key(day, user_id, "input")))
            cached_out = _as_int(cached.get(counter_key(day, user_id, "output")))
            if cached_in <= ledger_in and cached_out <= ledger_out:
                continue
            AITokenUsageLedger._default_manager.filter(pk=pk).update(
                input_tokens=Greatest(
                    F("input_tokens"),
                    Value(cached_in),
                    output_field=models.PositiveBigIntegerField(),
                ),
                output_tokens=Greatest(
                    F("output_tokens"),
                    Value(cached_out),
                    output_field=models.PositiveBigIntegerField(),
                ),
                updated_at=timezone.now(),
            )
            changed += 1


def clear_counters(user_id: Any, day: date) -> None:
    """Forget a user's cached totals for a day (used when its ledger row is deleted)."""
    try:
        cache.delete_many([counter_key(day, user_id, kind) for kind, _ in _FIELDS])
    except Exception as exc:
        logger.warning("Could not clear AI token counters: %s", exc)
