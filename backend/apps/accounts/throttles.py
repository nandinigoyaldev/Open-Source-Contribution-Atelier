"""
Rate-limiting throttle classes for authentication endpoints.

Uses DRF's built-in throttling system so there are zero extra dependencies.
All rates are configurable via settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'].

Proxy / Load-Balancer support
──────────────────────────────
When the app runs behind a reverse proxy (Nginx, AWS ALB, Cloudflare, etc.)
the real client IP is forwarded in the X-Forwarded-For header.
Set TRUSTED_PROXY_COUNT in settings (default 0) to the number of trusted proxy
hops so only the real client IP is used for throttle keys.
"""

import logging
import time
from typing import Tuple

from django.conf import settings as django_settings
from django.core.cache import cache
from rest_framework.throttling import SimpleRateThrottle

logger = logging.getLogger(__name__)

# Atomic Redis Lua script for rate limiting:
# KEYS[1]: rate limit cache key
# ARGV[1]: window duration in seconds
# ARGV[2]: max requests allowed
# Returns: {allowed (1 or 0), current_count, ttl_remaining}
LUA_RATE_LIMIT_SCRIPT = """
local key = KEYS[1]
local window = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])

local current = redis.call("INCR", key)
if current == 1 then
    redis.call("EXPIRE", key, window)
end

local ttl = redis.call("TTL", key)
if current > limit then
    return {0, current, ttl}
else
    return {1, current, ttl}
end
"""

_LUA_SHA = None


def get_redis_connection():
    """Retrieve raw redis client instance if available."""
    try:
        from django_redis import get_redis_connection as get_redis  # type: ignore

        return get_redis("default")
    except (ImportError, Exception):
        return None


class RedisLuaRateLimiter:
    """
    Atomic rate-limiter using Lua scripting over Redis.
    Guarantees atomic INCR + TTL assignment in a single operation across distributed workers.
    """

    def __init__(self, key: str, max_requests: int, window_seconds: int):
        self.key = key
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    def check(self) -> Tuple[bool, int, int]:
        """
        Executes the atomic Lua script.
        Returns: (allowed: bool, current_count: int, ttl_remaining: int)
        """
        global _LUA_SHA
        redis_client = get_redis_connection()

        if not redis_client:
            raise RuntimeError("Redis connection unavailable for Lua rate limiting")

        if _LUA_SHA is None:
            _LUA_SHA = redis_client.script_load(LUA_RATE_LIMIT_SCRIPT)

        try:
            res = redis_client.evalsha(
                _LUA_SHA, 1, self.key, self.window_seconds, self.max_requests
            )
        except Exception:
            # Re-register script if NOSCRIPT error occurs or client reset
            _LUA_SHA = redis_client.script_load(LUA_RATE_LIMIT_SCRIPT)
            res = redis_client.evalsha(
                _LUA_SHA, 1, self.key, self.window_seconds, self.max_requests
            )

        allowed = bool(res[0])
        current_count = int(res[1])
        ttl_remaining = int(res[2]) if res[2] and res[2] > 0 else self.window_seconds

        return allowed, current_count, ttl_remaining


from apps.core.throttling import SlidingWindowAnonThrottle


def _get_real_ip(request) -> str:
    """
    Extract the real client IP, accounting for trusted proxy hops using append-only semantics.

    Each trusted reverse proxy appends the remote IP it received the request from.
    With N trusted proxies, the real client IP is at index len(ips) - N.
    If TRUSTED_PROXY_COUNT is 0 or unconfigured, REMOTE_ADDR is returned directly.
    """
    trusted_hops = getattr(django_settings, "TRUSTED_PROXY_COUNT", 0)
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")

    if xff and trusted_hops > 0:
        ips = [ip.strip() for ip in xff.split(",") if ip.strip()]
        real_index = len(ips) - trusted_hops
        if 0 <= real_index < len(ips):
            return ips[real_index]

    return request.META.get("REMOTE_ADDR", "")


class BaseDistributedThrottle(SimpleRateThrottle):
    """
    Base throttle that uses Redis Lua scripting when settings.RATE_LIMIT_BACKEND == "redis".
    Falls back to local cache implementation if "local" or when Redis is down.
    """

    def get_rate(self):
        rates = getattr(django_settings, "REST_FRAMEWORK", {}).get(
            "DEFAULT_THROTTLE_RATES", {}
        )
        if hasattr(self, "scope") and self.scope in rates:
            return rates[self.scope]
        return super().get_rate()


class _ProxyAwareThrottle(SlidingWindowAnonThrottle):  # type: ignore
    """Base class that uses the proxy-aware IP resolver for cache keys."""

    num_requests: int  # type: ignore
    duration: int  # type: ignore

    def allow_request(self, request, view):
        if self.rate is None:
            return True

        self.key = self.get_cache_key(request, view)
        if self.key is None:
            return True

        if getattr(django_settings, "RATE_LIMIT_BACKEND", "local") == "redis":
            try:
                max_reqs = self.num_requests if self.num_requests is not None else 100
                win_secs = self.duration if self.duration is not None else 60

                limiter = RedisLuaRateLimiter(
                    key=self.key,
                    max_requests=max_reqs,
                    window_seconds=win_secs,
                )
                allowed, current_count, ttl = limiter.check()
                self.ttl = ttl
                return allowed
            except Exception as e:
                logger.warning(
                    f"Redis Lua throttle failed ({e}), falling back to local/cache throttle."
                )

        return self._allow_request_local(request, view)

    def _allow_request_local(self, request, view):
        self.history = cache.get(self.key, [])
        self.now = time.time()
        duration = self.duration if self.duration is not None else 60
        num_requests = self.num_requests if self.num_requests is not None else 100

        while self.history and self.history[-1] <= self.now - duration:
            self.history.pop()

        if len(self.history) >= num_requests:
            return self.throttle_failure()

        return self.throttle_success()

    def throttle_success(self):
        duration = self.duration if self.duration is not None else 60
        self.history.insert(0, self.now)
        cache.set(self.key, self.history, duration)
        return True

    def throttle_failure(self):
        return False

    def wait(self):
        if hasattr(self, "ttl"):
            return max(1, getattr(self, "ttl", 1))

        if hasattr(self, "history") and self.history:
            duration = self.duration if self.duration is not None else 60
            return max(1, int(duration - (self.now - self.history[-1])))
        return super().wait()


class UserRateThrottle(BaseDistributedThrottle):
    scope = "user"

    def allow_request(self, request, view):
        from apps.core.throttling import is_premium_user

        if not request.user or not request.user.is_authenticated:
            return True

        if is_premium_user(request.user):
            self.scope = "premium"
        else:
            self.scope = "user"

        self.rate = self.get_rate()
        if self.rate:
            self.num_requests, self.duration = self.parse_rate(self.rate)

        return super().allow_request(request, view)

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {"scope": self.scope, "ident": ident}


class PremiumRateThrottle(BaseDistributedThrottle):
    scope = "premium"

    def get_cache_key(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return None
        ident = request.user.pk
        return self.cache_format % {"scope": self.scope, "ident": ident}


class HeavyOperationRateThrottle(BaseDistributedThrottle):
    scope = "heavy_operation"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class AnonRateThrottle(BaseDistributedThrottle):
    scope = "anon"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return None

        ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class _ProxyAwareThrottle(AnonRateThrottle):
    def get_ident(self, request):
        return _get_real_ip(request)


class StrictIdentityLoginThrottle(SlidingWindowAnonThrottle):
    scope = "auth_login"

    def get_ident(self, request):
        identity = request.data.get("username")
        if identity:
            return str(identity).strip().lower()
        return _get_real_ip(request)


class LoginThrottle(_ProxyAwareThrottle):
    scope = "auth_login"


class SignupThrottle(_ProxyAwareThrottle):
    scope = "auth_signup"


class TokenRefreshThrottle(_ProxyAwareThrottle):
    scope = "auth_token_refresh"


class OtpGenerateThrottle(_ProxyAwareThrottle):
    scope = "auth_otp_generate"


class OtpVerifyThrottle(_ProxyAwareThrottle):
    scope = "auth_otp_verify"


class StrictIdentityPasswordResetThrottle(SlidingWindowAnonThrottle):
    scope = "auth_password_reset"

    def get_cache_key(self, request, view):
        # Anyone can name any address here, so being signed in does not skip the limit.
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }

    def get_ident(self, request):
        email = request.data.get("email")
        if email:
            return str(email).strip().lower()
        return _get_real_ip(request)


class PasswordResetThrottle(_ProxyAwareThrottle):
    scope = "auth_password_reset"

    def get_cache_key(self, request, view):
        # Same as above: these endpoints do not depend on who is signed in.
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class PasswordResetValidateThrottle(PasswordResetThrottle):
    scope = "auth_password_reset_validate"


class MagicLinkRequestThrottle(_ProxyAwareThrottle):
    scope = "auth_magic_link_request"


class StrictIdentityMagicLinkThrottle(SlidingWindowAnonThrottle):
    scope = "auth_magic_link_request"

    def get_ident(self, request):
        email = request.data.get("email")
        if email:
            return str(email).strip().lower()
        return _get_real_ip(request)


class MagicLinkVerifyThrottle(_ProxyAwareThrottle):
    scope = "auth_magic_link_verify"


class EmailVerifyThrottle(_ProxyAwareThrottle):
    scope = "auth_email_verify"


class ResendVerificationThrottle(_ProxyAwareThrottle):
    scope = "auth_email_verification_resend"


class StrictIdentityResendVerificationThrottle(SlidingWindowAnonThrottle):
    scope = "auth_email_verification_resend"

    def get_ident(self, request):
        email = request.data.get("email")
        if email:
            return str(email).strip().lower()
        # A resend from an expired link has no email. Falling back to the IP
        # would land in the same bucket as ResendVerificationThrottle and
        # count every request twice, so use the link's payload (the account
        # it was issued for) instead.
        key = request.data.get("key")
        if key:
            return "key:" + str(key).split(":", 1)[0][:200]
        return _get_real_ip(request)


class OAuthThrottle(_ProxyAwareThrottle):
    scope = "auth_oauth"


class GitHubOAuthCallbackThrottle(_ProxyAwareThrottle):
    scope = "auth_github_callback"
