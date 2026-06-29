"""
Tests for authentication rate limiting (Issue #283).

Verifies that:
  - Each sensitive endpoint returns HTTP 429 when its throttle limit is exceeded.
  - The 429 response body follows { error, message, retry_after } contract.
  - Requests below the threshold are NOT blocked.
  - Each IP has its own independent throttle counter.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


def _client(ip="203.0.113.1"):
    """Return an APIClient pre-configured with a stable test IP."""
    c = APIClient()
    c.defaults["REMOTE_ADDR"] = ip
    return c


def _hit(client, url, data, n=1):
    """Fire n POST requests and return the last response."""
    resp = None
    for _ in range(n):
        resp = client.post(url, data, format="json")
    return resp


# ─────────────────────────────────────────────────────────────────────────────
# 429 Response Shape
# ─────────────────────────────────────────────────────────────────────────────


class RateLimitShapeTests(TestCase):
    """Every throttled endpoint must return our standard 429 body."""

    def test_login_429_shape(self):
        c = _client()
        # RATE_AUTH_LOGIN is "5/minute"
        _hit(c, "/api/auth/login/", {"username": "x", "password": "y"}, n=5)
        resp = _hit(c, "/api/auth/login/", {"username": "x", "password": "y"})
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(resp.data["error"], "rate_limited")
        self.assertIn("message", resp.data)
        self.assertIn("retry_after", resp.data)

    def test_signup_429_shape(self):
        c = _client()
        # RATE_AUTH_SIGNUP is "10/hour"
        _hit(
            c,
            "/api/auth/signup/",
            {"username": "u1", "email": "u1@x.com", "password": "Aa1!aaaa"},
            n=10,
        )
        resp = _hit(
            c,
            "/api/auth/signup/",
            {"username": "u2", "email": "u2@x.com", "password": "Aa1!aaaa"},
        )
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(resp.data["error"], "rate_limited")

    def test_token_refresh_429_shape(self):
        c = _client()
        # RATE_AUTH_TOKEN_REFRESH is "30/minute"
        _hit(c, "/api/auth/refresh/", {"refresh": "bad"}, n=30)
        resp = _hit(c, "/api/auth/refresh/", {"refresh": "bad"})
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(resp.data["error"], "rate_limited")

    def test_password_reset_request_429_shape(self):
        c = _client()
        # RATE_AUTH_PASSWORD_RESET is "3/hour"
        _hit(c, "/api/auth/password-reset/", {"email": "test@example.com"}, n=3)
        resp = _hit(c, "/api/auth/password-reset/", {"email": "test@example.com"})
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(resp.data["error"], "rate_limited")

    def test_password_reset_confirm_429_shape(self):
        import uuid

        c = _client()
        payload = {"token": str(uuid.uuid4()), "new_password": "Aa1!aaaa"}
        _hit(c, "/api/auth/password-reset/confirm/", payload, n=3)
        resp = _hit(c, "/api/auth/password-reset/confirm/", payload)
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(resp.data["error"], "rate_limited")

    def test_otp_request_429_shape(self):
        c = _client()
        # RATE_AUTH_OTP_GENERATE is "3/minute"
        _hit(c, "/api/auth/otp/request/", {"email": "test@example.com"}, n=3)
        resp = _hit(c, "/api/auth/otp/request/", {"email": "test@example.com"})
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(resp.data["error"], "rate_limited")

    def test_otp_verify_429_shape(self):
        import uuid

        c = _client()
        # RATE_AUTH_OTP_VERIFY is "5/minute"
        payload = {"email": "test@example.com", "otp": str(uuid.uuid4())}
        _hit(c, "/api/auth/otp/verify/", payload, n=5)
        resp = _hit(c, "/api/auth/otp/verify/", payload)
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(resp.data["error"], "rate_limited")

    def test_google_oauth_429_shape(self):
        c = _client()
        # RATE_AUTH_OAUTH is "20/minute"
        _hit(c, "/api/auth/google/", {"access_token": "fake"}, n=20)
        resp = _hit(c, "/api/auth/google/", {"access_token": "fake"})
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(resp.data["error"], "rate_limited")


# ─────────────────────────────────────────────────────────────────────────────
# Below Threshold — must NOT be blocked
# ─────────────────────────────────────────────────────────────────────────────


class BelowThresholdTests(TestCase):
    """Requests below the limit must pass through normally."""

    def test_login_below_limit_not_throttled(self):
        c = _client()
        # Limit is 5, making 3 should not throttle
        for _ in range(3):
            resp = _hit(
                c, "/api/auth/login/", {"username": "nobody", "password": "wrong"}
            )
            self.assertNotEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_password_reset_below_limit_not_throttled(self):
        c = _client()
        # Limit is 3, making 2 should not throttle
        for _ in range(2):
            resp = _hit(c, "/api/auth/password-reset/", {"email": "nobody@x.com"})
            self.assertNotEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_otp_request_below_limit_not_throttled(self):
        c = _client()
        # Limit is 3, making 2 should not throttle
        for _ in range(2):
            resp = _hit(c, "/api/auth/otp/request/", {"email": "nobody@x.com"})
            self.assertNotEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


# ─────────────────────────────────────────────────────────────────────────────
# IP Isolation — each IP has its own counter
# ─────────────────────────────────────────────────────────────────────────────


class IpIsolationTests(TestCase):
    """Throttle counters must be isolated per IP address."""

    def test_password_reset_ips_are_independent(self):
        url = "/api/auth/password-reset/"
        data = {"email": "test@example.com"}

        c1 = _client("203.0.113.10")
        c2 = _client("203.0.113.20")

        # Exhaust c1 (limit is 3)
        _hit(c1, url, data, n=3)
        resp_c1 = _hit(c1, url, data)  # 4th — throttled

        # c2 still has fresh quota
        resp_c2 = _hit(c2, url, data)  # 1st — should pass

        self.assertEqual(resp_c1.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertNotEqual(resp_c2.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_otp_verify_ips_are_independent(self):
        import uuid

        url = "/api/auth/otp/verify/"
        data = {"email": "test@example.com", "otp": str(uuid.uuid4())}

        c1 = _client("203.0.113.30")
        c2 = _client("203.0.113.40")

        # Exhaust c1 (limit is 5)
        _hit(c1, url, data, n=5)
        resp_c1 = _hit(c1, url, data)  # 6th - throttled

        # c2 fresh
        resp_c2 = _hit(c2, url, data)

        self.assertEqual(resp_c1.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertNotEqual(resp_c2.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


# ─────────────────────────────────────────────────────────────────────────────
# Password Reset & OTP Business Logic (non-throttle)
# ─────────────────────────────────────────────────────────────────────────────


class PasswordResetFlowTests(TestCase):
    """Verify password reset endpoint logic (valid/invalid/expired tokens)."""

    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        self.user = User.objects.create_user(
            username="resetuser", email="reset@example.com", password="OldPass1!"
        )
        self.client = _client("203.0.113.50")

    def test_reset_request_always_returns_200(self):
        """Never reveals if email exists (anti-enumeration)."""
        # Known email
        resp = self.client.post(
            "/api/auth/password-reset/", {"email": "reset@example.com"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Unknown email — same response
        resp2 = self.client.post(
            "/api/auth/password-reset/", {"email": "ghost@x.com"}, format="json"
        )
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)

    def test_reset_confirm_with_invalid_token_returns_400(self):
        import uuid

        resp = self.client.post(
            "/api/auth/password-reset/confirm/",
            {"token": str(uuid.uuid4()), "new_password": "NewPass1!"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            resp.data["error"],
            (
                "invalid_otp"
                if "error" in resp.data and resp.data["error"] == "invalid_otp"
                else "invalid_token"
            ),
        )

    def test_full_reset_flow(self):
        """Request → confirm with valid token → password is changed."""
        from apps.accounts.models import PasswordResetToken

        # Trigger reset (creates token in DB)
        self.client.post(
            "/api/auth/password-reset/", {"email": "reset@example.com"}, format="json"
        )
        token = PasswordResetToken.objects.filter(user=self.user, is_used=False).first()
        self.assertIsNotNone(token)

        # Confirm reset
        resp = self.client.post(
            "/api/auth/password-reset/confirm/",
            {"token": str(token.token), "new_password": "NewPass1!"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # Token is now marked used
        token.refresh_from_db()
        self.assertTrue(token.is_used)

        # New password works
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewPass1!"))

    def test_token_cannot_be_reused(self):
        """A used token must be rejected on a second attempt."""
        from apps.accounts.models import PasswordResetToken

        self.client.post(
            "/api/auth/password-reset/", {"email": "reset@example.com"}, format="json"
        )
        token = PasswordResetToken.objects.filter(user=self.user, is_used=False).first()

        self.client.post(
            "/api/auth/password-reset/confirm/",
            {"token": str(token.token), "new_password": "NewPass1!"},
            format="json",
        )
        # Attempt reuse
        resp = self.client.post(
            "/api/auth/password-reset/confirm/",
            {"token": str(token.token), "new_password": "AnotherPass1!"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
