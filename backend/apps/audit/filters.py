"""
Query-parameter filters for the admin audit log list (``GET /api/admin/audit/``).

``parse_audit_filters`` turns the request's query string into clean values or a dict of
field errors, so the view can answer 400 with a message per field instead of quietly
ignoring a bad value or failing with a 500.

Date rules
    * ``start_date`` / ``end_date`` take ``YYYY-MM-DD`` or an ISO 8601 date-time.
    * A date without a time covers the whole day: ``start_date=2026-01-01`` starts at
      00:00 and ``end_date=2026-01-31`` ends at the end of the 31st (the bound is the
      start of the next day, exclusive). A date-time bound is used exactly as given.
    * Dates are read in the server's configured time zone unless they carry an offset.
    * ``start_date`` later than ``end_date`` is an error.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Optional

from django.utils.dateparse import parse_date, parse_datetime
from django.utils.timezone import is_aware, make_aware

from apps.audit.models import AuditEvent

VALID_ACTIONS = tuple(value for value, _label in AuditEvent.ACTION_CHOICES)
MAX_TEXT_FILTER_LENGTH = 100

DATE_HELP = "Enter a valid date (YYYY-MM-DD) or ISO 8601 date-time."


@dataclass(frozen=True)
class AuditFilters:
    """Validated filter values. ``None`` or ``""`` means that filter is not applied."""

    start: Optional[datetime] = None
    end: Optional[datetime] = None
    end_inclusive: bool = True
    action: str = ""
    operation: str = ""
    actor: str = ""
    resource_type: str = ""
    resource_id: str = ""
    correlation_id: str = ""
    search: str = ""


def _parse_bound(raw: str) -> tuple[datetime, bool]:
    """Return ``(moment, date_only)`` or raise ``ValueError`` for an unusable value."""
    text = raw.strip().replace("Z", "+00:00")
    # A plain date, with no time part, covers its whole day.
    if "T" not in text and " " not in text:
        day = parse_date(text)
        if day is None:
            raise ValueError(raw)
        return make_aware(datetime.combine(day, time.min)), True
    moment = parse_datetime(text)
    if moment is None:
        raise ValueError(raw)
    return (moment if is_aware(moment) else make_aware(moment)), False


def _date_bound(params, name: str, errors: dict) -> tuple[Optional[datetime], bool]:
    raw = params.get(name)
    if raw is None or not str(raw).strip():
        return None, False
    try:
        return _parse_bound(str(raw))
    except (ValueError, OverflowError):
        errors[name] = [DATE_HELP]
        return None, False


def _text(params, errors: dict, *names: str) -> str:
    """First non-empty value among ``names`` (aliases), stripped; too long is an error."""
    for name in names:
        value = (params.get(name) or "").strip()
        if value:
            if len(value) > MAX_TEXT_FILTER_LENGTH:
                errors[name] = [f"Use at most {MAX_TEXT_FILTER_LENGTH} characters."]
                return ""
            return value
    return ""


def parse_audit_filters(params) -> tuple[AuditFilters, dict]:
    """Validate the query parameters. Returns ``(filters, errors)``; use the filters only if ``errors`` is empty."""
    errors: dict = {}

    start, _ = _date_bound(params, "start_date", errors)
    end, end_date_only = _date_bound(params, "end_date", errors)
    if end is not None and end_date_only:
        end += timedelta(days=1)
    if (
        start is not None
        and end is not None
        and "start_date" not in errors
        and "end_date" not in errors
    ):
        # compare against the inclusive end of the range (the previous instant for a whole-day end)
        last_moment = end - timedelta(microseconds=1) if end_date_only else end
        if start > last_moment:
            errors["end_date"] = ["End date must not be before the start date."]

    action = (params.get("action") or "").strip().lower()
    if action and action not in VALID_ACTIONS:
        errors["action"] = [f"Choose one of: {', '.join(VALID_ACTIONS)}."]
        action = ""

    filters = AuditFilters(
        start=start,
        end=end,
        end_inclusive=not end_date_only,
        action=action,
        operation=_text(params, errors, "operation"),
        actor=_text(params, errors, "actor"),
        resource_type=_text(params, errors, "resource_type", "model_type"),
        resource_id=_text(params, errors, "resource_id"),
        correlation_id=_text(params, errors, "correlation_id"),
        search=_text(params, errors, "search", "q"),
    )
    return filters, errors
