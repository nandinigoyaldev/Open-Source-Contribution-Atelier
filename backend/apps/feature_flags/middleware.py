"""Attach a guest-safe feature-flag accessor to every request.

Flags live in two places: the database-backed ``FeatureFlag`` model (with
environment scoping, rollout, targeting and a kill switch) and django-waffle
for older flags. ``waffle.flag_is_active`` already evaluates flags for
unauthenticated requests -- a flag's ``everyone`` / ``percent`` rollout applies
to ``AnonymousUser`` too (percent rollouts use a sticky cookie for guests).
This middleware guarantees that ``request.feature_flags`` is always present
with an ``is_enabled(flag_name)`` helper, including on guest visits, so views
can call ``request.feature_flags.is_enabled("new_landing")`` without guarding
against ``AttributeError``.

Safe default: when the flag table cannot be read (database down, missing
migration), the flag is evaluated from its last-known state in the cache. If
there is no last-known state either, the flag is off
(``settings.WAFFLE_FLAG_DEFAULT``).
"""

from __future__ import annotations

import logging

import waffle
from django.conf import settings
from django.db import DatabaseError

from apps.feature_flags.models import FeatureFlag
from apps.feature_flags.services import (
    evaluate_feature_flag,
    last_known_flag,
    remember_flag_state,
)

logger = logging.getLogger(__name__)


def _safe_default() -> bool:
    return bool(getattr(settings, "WAFFLE_FLAG_DEFAULT", False))


class FeatureFlags:
    """Request-scoped, read-only accessor over feature flags."""

    __slots__ = ("_request",)

    def __init__(self, request):
        self._request = request

    def _evaluate(self, flag: FeatureFlag) -> bool:
        user = getattr(self._request, "user", None)
        org = getattr(self._request, "organization", None) or getattr(
            self._request, "tenant", None
        )
        enabled, _ = evaluate_feature_flag(flag, user=user, organization=org)
        return enabled

    def is_enabled(self, flag_name: str) -> bool:
        """Return whether ``flag_name`` is active for this request.

        Works identically for authenticated users and ``AnonymousUser``.
        A database-backed FeatureFlag wins; otherwise django-waffle decides.
        Unknown flags evaluate to ``settings.WAFFLE_FLAG_DEFAULT`` (``False``
        unless overridden).
        """
        try:
            flag = FeatureFlag.objects.filter(name=flag_name).first()
        except DatabaseError:
            cached = last_known_flag(flag_name)
            logger.warning(
                "Feature flag store unavailable, using %s for %s",
                "last-known state" if cached else "safe default",
                flag_name,
            )
            return self._evaluate(cached) if cached else _safe_default()

        if flag is not None:
            remember_flag_state(flag)
            return self._evaluate(flag)

        try:
            return bool(waffle.flag_is_active(self._request, flag_name))
        except DatabaseError:
            logger.warning("Waffle unavailable, using safe default for %s", flag_name)
            return _safe_default()


class FeatureFlagsMiddleware:
    """Populate ``request.feature_flags`` on every request, guest or not."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.feature_flags = FeatureFlags(request)
        return self.get_response(request)
