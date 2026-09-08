"""Attach a guest-safe feature-flag accessor to every request.

Feature flags are managed by django-waffle. ``waffle.flag_is_active`` already
evaluates flags for unauthenticated requests -- a flag's ``everyone`` /
``percent`` rollout applies to ``AnonymousUser`` too (percent rollouts use a
sticky cookie for guests) -- so this middleware does not re-implement any
evaluation logic. It only guarantees that ``request.feature_flags`` is always
present with an ``is_enabled(flag_name)`` helper, including on guest visits,
so views can call ``request.feature_flags.is_enabled("new_landing")`` without
guarding against ``AttributeError``.
"""

from __future__ import annotations

import waffle


class FeatureFlags:
    """Request-scoped, read-only accessor over django-waffle flags."""

    __slots__ = ("_request",)

    def __init__(self, request):
        self._request = request

    def is_enabled(self, flag_name: str) -> bool:
        """Return whether ``flag_name`` is active for this request.

        Works identically for authenticated users and ``AnonymousUser``.
        Unknown flags evaluate to ``settings.WAFFLE_FLAG_DEFAULT`` (``False``
        unless overridden).
        """
        return bool(waffle.flag_is_active(self._request, flag_name))


class FeatureFlagsMiddleware:
    """Populate ``request.feature_flags`` on every request, guest or not."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.feature_flags = FeatureFlags(request)
        return self.get_response(request)
