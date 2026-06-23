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

Endpoint throttle map
─────────────────────
  LoginThrottle         → 5 attempts/minute per IP   (brute-force protection)
  SignupThrottle        → 10 requests/hour  per IP   (registration abuse)
  TokenRefreshThrottle  → 30 requests/minute per IP  (refresh flood)
  OtpGenerateThrottle   → 3 requests/minute per IP   (OTP/email spam)
  OtpVerifyThrottle     → 5 attempts/minute per IP   (OTP guessing)
  PasswordResetThrottle → 3 requests/hour   per IP   (email spam)
  OAuthThrottle         → 20 requests/minute per IP  (OAuth abuse)
"""

from django.conf import settings as django_settings
from rest_framework.throttling import AnonRateThrottle


def _get_real_ip(request) -> str:
    """
    Extract the real client IP, accounting for trusted proxy hops.

    When TRUSTED_PROXY_COUNT = N, the Nth IP from the right of X-Forwarded-For
    is used (the last N IPs are injected by trusted infrastructure, so we skip them).
    Falls back to REMOTE_ADDR when the header is absent.
    """
    trusted_hops = getattr(django_settings, "TRUSTED_PROXY_COUNT", 0)
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")

    if xff and trusted_hops > 0:
        # XFF is a comma-separated list: client, proxy1, proxy2, …
        ips = [ip.strip() for ip in xff.split(",") if ip.strip()]
        # The real client is at index: len(ips) - trusted_hops - 1
        real_index = len(ips) - trusted_hops - 1
        if 0 <= real_index < len(ips):
            return ips[real_index]

    # Default: use REMOTE_ADDR (direct connection or single trusted proxy)
    return request.META.get("REMOTE_ADDR", "")


class _ProxyAwareThrottle(AnonRateThrottle):
    """Base class that uses the proxy-aware IP resolver for cache keys."""

    def get_ident(self, request):
        return _get_real_ip(request)


class StrictIdentityLoginThrottle(AnonRateThrottle):
    scope = "auth_login"

    def get_ident(self, request):
        identity = request.data.get("email") or request.data.get("username")
        if identity:
            return str(identity).strip().lower()
        return _get_real_ip(request)


# ─────────────────────────────────────────────────────────────────────────────
# Login – strict IP-based limit to block brute-force credential attacks
# ─────────────────────────────────────────────────────────────────────────────
class LoginThrottle(_ProxyAwareThrottle):
    scope = "auth_login"


# ─────────────────────────────────────────────────────────────────────────────
# Signup – prevent bulk account registration / farming
# ─────────────────────────────────────────────────────────────────────────────
class SignupThrottle(_ProxyAwareThrottle):
    scope = "auth_signup"


# ─────────────────────────────────────────────────────────────────────────────
# Token refresh – allow normal client refreshes but cap flood attacks
# ─────────────────────────────────────────────────────────────────────────────
class TokenRefreshThrottle(_ProxyAwareThrottle):
    scope = "auth_token_refresh"


# ─────────────────────────────────────────────────────────────────────────────
# OTP generation – tightly capped to prevent email/SMS spam
# ─────────────────────────────────────────────────────────────────────────────
class OtpGenerateThrottle(_ProxyAwareThrottle):
    scope = "auth_otp_generate"


# ─────────────────────────────────────────────────────────────────────────────
# OTP verification – prevent brute-force guessing of one-time codes
# ─────────────────────────────────────────────────────────────────────────────
class OtpVerifyThrottle(_ProxyAwareThrottle):
    scope = "auth_otp_verify"


class StrictIdentityPasswordResetThrottle(AnonRateThrottle):
    scope = "auth_password_reset"

    def get_ident(self, request):
        email = request.data.get("email")
        if email:
            return str(email).strip().lower()
        return _get_real_ip(request)


class StrictIdentityPasswordResetThrottle(AnonRateThrottle):
    scope = "auth_password_reset"

    def get_ident(self, request):
        email = request.data.get("email")
        if email:
            return str(email).strip().lower()
        return _get_real_ip(request)


# ─────────────────────────────────────────────────────────────────────────────
# Password reset – prevent email bombing / enumeration attacks
# ─────────────────────────────────────────────────────────────────────────────
class PasswordResetThrottle(_ProxyAwareThrottle):
    scope = "auth_password_reset"


# ─────────────────────────────────────────────────────────────────────────────
# Magic link – prevent email bombing and token guessing
# ─────────────────────────────────────────────────────────────────────────────
class MagicLinkRequestThrottle(_ProxyAwareThrottle):
    scope = "auth_magic_link_request"


class StrictIdentityMagicLinkThrottle(AnonRateThrottle):
    scope = "auth_magic_link_request"

    def get_ident(self, request):
        email = request.data.get("email")
        if email:
            return str(email).strip().lower()
        return _get_real_ip(request)


class MagicLinkVerifyThrottle(_ProxyAwareThrottle):
    scope = "auth_magic_link_verify"


# ─────────────────────────────────────────────────────────────────────────────
# OAuth (Google / GitHub) – cap automated OAuth token abuse
# ─────────────────────────────────────────────────────────────────────────────
class OAuthThrottle(_ProxyAwareThrottle):
    scope = "auth_oauth"
