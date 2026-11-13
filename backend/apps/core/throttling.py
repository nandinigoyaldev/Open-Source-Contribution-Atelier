import logging
import math
import time
import uuid
from typing import List, Optional, TypedDict

from django.core.cache import cache
from rest_framework.exceptions import Throttled
from rest_framework.throttling import SimpleRateThrottle

logger = logging.getLogger(__name__)


def get_redis_connection():
    try:
        from django_redis import get_redis_connection as get_redis  # type: ignore

        return get_redis("default")
    except (ImportError, NotImplementedError):
        return None


def is_premium_user(user) -> bool:
    """
    Returns True if the user has premium status.
    Checks:
    1. Superuser / Staff / user.is_premium attribute
    2. user.tier attribute in ("premium", "pro", "enterprise")
    3. Active subscription in CustomerSubscription model
    """
    if not user or not user.is_authenticated:
        return False

    if (
        getattr(user, "is_superuser", False)
        or getattr(user, "is_staff", False)
        or getattr(user, "is_premium", False)
    ):
        return True

    tier = getattr(user, "tier", None)
    if tier and str(tier).lower() in ("premium", "pro", "enterprise"):
        return True

    try:
        from apps.billing.models import CustomerSubscription

        return CustomerSubscription.objects.filter(user=user, active=True).exists()
    except Exception:
        return False


class RateLimitState(TypedDict):
    """What a client needs to know about one limit that applied to a request."""

    limit: int
    remaining: int
    reset: int  # seconds until this limit next frees capacity


def _http_request(request):
    """DRF wraps the Django request; the middleware only sees the wrapped one."""
    return getattr(request, "_request", request)


def record_rate_limit_state(request, state: RateLimitState) -> None:
    """Remember a limit that applied to this request so the response can report it."""
    states = getattr(_http_request(request), "_throttle_states", None)
    if states is None:
        states = []
        setattr(_http_request(request), "_throttle_states", states)
    states.append(state)


def get_rate_limit_states(request) -> List[RateLimitState]:
    return list(getattr(_http_request(request), "_throttle_states", None) or [])


def most_restrictive(states) -> Optional[RateLimitState]:
    """
    Pick the limit a client should plan around: the one with the least
    capacity left. On a tie the one that resets last wins, so a client that
    waits for `reset` is never told to retry while another limit still blocks.
    """
    states = [s for s in states if s]
    if not states:
        return None
    return min(states, key=lambda s: (s["remaining"], -s["reset"], s["limit"]))


def set_rate_limit_headers(response, state: Optional[RateLimitState], now=None):
    """
    X-RateLimit-Limit: requests allowed in the window
    X-RateLimit-Remaining: requests left in it
    X-RateLimit-Reset: unix time (seconds) at which capacity is next freed
    """
    if not state:
        return
    now = time.time() if now is None else now
    response["X-RateLimit-Limit"] = str(state["limit"])
    response["X-RateLimit-Remaining"] = str(state["remaining"])
    response["X-RateLimit-Reset"] = str(int(now + state["reset"]))


def record_throttle_state(request, throttle, allowed: bool) -> None:
    """
    Snapshot a DRF throttle after allow_request() ran. Throttles that did not
    apply to the request (no rate, no cache key, anonymous-only for a signed in
    user, ...) never set up a window and are skipped.
    """
    if allowed and not getattr(throttle, "expose_rate_limit_state", True):
        return
    limit = getattr(throttle, "num_requests", None)
    duration = getattr(throttle, "duration", None)
    if not limit or not duration or getattr(throttle, "key", None) is None:
        return

    now = getattr(throttle, "now", None) or time.time()
    used = getattr(throttle, "rl_used", None)
    oldest = getattr(throttle, "rl_oldest", None)
    if used is None:
        history = getattr(throttle, "history", None)
        if history is None:
            return
        used = len(history)
        oldest = history[-1] if history else None

    remaining = 0 if not allowed else max(0, limit - used)
    reset = duration if oldest is None else oldest + duration - now
    record_rate_limit_state(
        request,
        {
            "limit": int(limit),
            "remaining": int(remaining),
            "reset": max(1, int(math.ceil(reset))),
        },
    )


class ThrottleStateMixin:
    """Put in front of a DRF throttle to report its state on the response."""

    def allow_request(self, request, view):
        try:
            allowed = super().allow_request(request, view)  # type: ignore[misc]
        except Throttled:
            record_throttle_state(request, self, False)
            raise
        record_throttle_state(request, self, allowed)
        return allowed


class SlidingWindowThrottle(SimpleRateThrottle):
    """
    Rate throttle using sliding window algorithm via Redis sorted sets.
    """

    num_requests: Optional[int] = None
    duration: Optional[int] = None
    oldest_score: Optional[float] = None

    def allow_request(self, request, view):
        try:
            allowed = self._check_request(request, view)
        except Throttled:
            # throttle_failure() may raise instead of returning False
            record_throttle_state(request, self, False)
            raise
        record_throttle_state(request, self, allowed)
        return allowed

    def _check_request(self, request, view):
        """
        Implement sliding window rate limiting.
        """
        self.rl_used = None
        self.rl_oldest = None
        if self.rate is None:
            return True

        self.key = self.get_cache_key(request, view)
        if self.key is None:
            return True

        self.history = []

        redis_client = get_redis_connection()
        if not redis_client:
            return super().allow_request(request, view)

        self.now = time.time()
        duration = self.duration if self.duration is not None else 3600
        num_requests = self.num_requests if self.num_requests is not None else 1000

        cutoff = self.now - duration
        member_id = f"{self.now}:{uuid.uuid4().hex}"

        try:
            pipeline = redis_client.pipeline()
            pipeline.zremrangebyscore(self.key, 0, cutoff)
            pipeline.zadd(self.key, {member_id: self.now})
            pipeline.zcard(self.key)
            pipeline.expire(self.key, duration)
            pipeline.zrange(self.key, 0, 0, withscores=True)
            results = pipeline.execute()

            count = results[2]
            self.rl_used = count
            if len(results) > 4 and results[4]:
                self.rl_oldest = results[4][0][1]

            if count > num_requests:
                redis_client.zrem(self.key, member_id)
                oldest = redis_client.zrange(self.key, 0, 0, withscores=True)
                if oldest:
                    self.oldest_score = oldest[0][1]
                else:
                    self.oldest_score = self.now
                self.rl_oldest = self.oldest_score
                return False

            return True
        except Exception as e:
            logger.error(f"Redis rate limiting failed: {e}")
            self.rl_used = None
            self.rl_oldest = None
            return super().allow_request(request, view)

    def wait(self):
        """
        Returns the recommended number of seconds to wait before the next request.
        """
        duration = self.duration if self.duration is not None else 3600
        if self.oldest_score is not None:
            wait_time = duration - (self.now - self.oldest_score)
            return max(1, int(wait_time))
        return super().wait()


class SlidingWindowAnonThrottle(SlidingWindowThrottle):
    scope = "anon"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class SlidingWindowUserThrottle(SlidingWindowThrottle):
    scope = "user"

    def allow_request(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return True

        if is_premium_user(request.user):
            self.scope = "premium"
        else:
            self.scope = "user"

        self.rate = self.get_rate()
        if self.rate:
            num_requests, duration = self.parse_rate(self.rate)
            self.num_requests = num_requests
            self.duration = duration

        return super().allow_request(request, view)

    def get_cache_key(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return None

        ident = getattr(request.user, "pk", getattr(request.user, "id", None))
        return self.cache_format % {"scope": self.scope, "ident": ident}


class SlidingWindowPremiumThrottle(SlidingWindowThrottle):
    scope = "premium"

    def get_cache_key(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return None
        ident = getattr(request.user, "pk", getattr(request.user, "id", None))
        return self.cache_format % {"scope": self.scope, "ident": ident}


class HeavyOperationThrottle(SlidingWindowThrottle):
    scope = "heavy_operation"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = getattr(request.user, "pk", getattr(request.user, "id", None))
        else:
            ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class SlidingWindowScopedThrottle(SlidingWindowThrottle):
    scope_attr = "throttle_scope"

    def __init__(self):
        pass

    def allow_request(self, request, view):
        self.scope = getattr(view, self.scope_attr, None)
        if not self.scope:
            return True

        self.rate = self.get_rate()
        if not self.rate:
            return True

        num_requests, duration = self.parse_rate(self.rate)
        self.num_requests = num_requests
        self.duration = duration

        return super().allow_request(request, view)

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = getattr(request.user, "pk", getattr(request.user, "id", None))
        else:
            ident = self.get_ident(request)

        return self.cache_format % {"scope": self.scope, "ident": ident}
