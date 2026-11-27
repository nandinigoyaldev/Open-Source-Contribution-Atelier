from datetime import timezone as dt_timezone
from typing import Dict, Optional

from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from apps.core.throttling import ThrottleStateMixin

from .token_budget import SCOPE_ORGANIZATION, BudgetStatus


class AiTutorRateThrottle(ThrottleStateMixin, UserRateThrottle):
    """Limit AI Tutor queries to protect the upstream AI token budget."""

    scope = "ai_tutor"

    def get_rate(self):
        from django.conf import settings

        rates = getattr(settings, "REST_FRAMEWORK", {}).get(
            "DEFAULT_THROTTLE_RATES", {}
        )
        return rates.get(self.scope)

    def allow_request(self, request, view):
        self.rate = self.get_rate()
        self.num_requests, self.duration = self.parse_rate(self.rate)
        return super().allow_request(request, view)


# ------------------------------------------------------------ daily token budget
# The request throttle above counts requests. The daily token budget counts what
# those requests cost; see token_budget.py.

TOKEN_BUDGET_LIMIT_HEADER = "X-AI-Token-Budget-Limit"
TOKEN_BUDGET_REMAINING_HEADER = "X-AI-Token-Budget-Remaining"
TOKEN_BUDGET_RESET_HEADER = "X-AI-Token-Budget-Reset"
TOKEN_BUDGET_SCOPE_HEADER = "X-AI-Token-Budget-Scope"
TOKEN_BUDGET_WARNING_HEADER = "X-AI-Token-Budget-Warning"

TOKEN_BUDGET_HEADERS = [
    TOKEN_BUDGET_LIMIT_HEADER,
    TOKEN_BUDGET_REMAINING_HEADER,
    TOKEN_BUDGET_RESET_HEADER,
    TOKEN_BUDGET_SCOPE_HEADER,
    TOKEN_BUDGET_WARNING_HEADER,
]


def token_budget_headers(budget: BudgetStatus) -> Dict[str, str]:
    headers = {
        TOKEN_BUDGET_LIMIT_HEADER: str(budget.limit),
        TOKEN_BUDGET_REMAINING_HEADER: str(budget.remaining),
        # Unix time, like X-RateLimit-Reset
        TOKEN_BUDGET_RESET_HEADER: str(int(budget.reset_at.timestamp())),
        TOKEN_BUDGET_SCOPE_HEADER: budget.scope,
    }
    if budget.warning:
        headers[TOKEN_BUDGET_WARNING_HEADER] = (
            f"{budget.percent_used}% of the daily AI tutor token budget used"
        )
    return headers


def add_token_budget_headers(response, budget: Optional[BudgetStatus]):
    if budget is not None:
        for name, value in token_budget_headers(budget).items():
            response[name] = value
    return response


def token_budget_exceeded_response(budget: BudgetStatus, now=None) -> Response:
    """429 for a user (or organization) that used up today's token budget."""
    retry_after = budget.retry_after_seconds(now)
    if budget.scope == SCOPE_ORGANIZATION:
        message = "Your organization has used today's shared AI tutor token budget."
    else:
        message = "You have used today's AI tutor token budget."
    data = {
        "error": "ai_token_budget_exhausted",
        "code": "ai_token_budget_exhausted",
        "message": f"{message} It resets at midnight UTC.",
        "limit": budget.limit,
        "used": budget.used,
        "remaining": 0,
        "tier": budget.tier,
        "scope": budget.scope,
        "reset_at": budget.reset_at.astimezone(dt_timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "retry_after": retry_after,
    }
    response = Response(data, status=status.HTTP_429_TOO_MANY_REQUESTS)
    response["Retry-After"] = str(retry_after)
    return add_token_budget_headers(response, budget)
