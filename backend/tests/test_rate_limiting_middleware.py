import time
from unittest import mock

import redis
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.cache.backends.base import CacheKeyWarning
from django.http import JsonResponse
from django.test import RequestFactory, TestCase, override_settings
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.middleware.ratelimit import (
    RateLimitMiddleware,
    _get_client_ip,
    _parse_rate,
)

User = get_user_model()


class RateLimitMiddlewareTests(TestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()
        self.user1 = User.objects.create_user(username="user1", password="password123")
        self.user2 = User.objects.create_user(username="user2", password="password123")
        self.premium_user = User.objects.create_user(
            username="prem_user", password="password123", is_staff=True
        )

    def tearDown(self):
        cache.clear()

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Rate Parsing Helper Tests
    # ─────────────────────────────────────────────────────────────────────────

    def test_parse_rate_helper(self):
        limit, window = _parse_rate("5/minute", default_limit=10)
        self.assertEqual(limit, 5)
        self.assertEqual(window, 60)

        limit, window = _parse_rate("60/minute", default_limit=10)
        self.assertEqual(limit, 60)
        self.assertEqual(window, 60)

        limit, window = _parse_rate("20/minute", default_limit=10)
        self.assertEqual(limit, 20)
        self.assertEqual(window, 60)

        limit, window = _parse_rate("100/hour", default_limit=10)
        self.assertEqual(limit, 100)
        self.assertEqual(window, 3600)

        limit, window = _parse_rate("10/second", default_limit=10)
        self.assertEqual(limit, 10)
        self.assertEqual(window, 1)

        limit, window = _parse_rate("1000/day", default_limit=10)
        self.assertEqual(limit, 1000)
        self.assertEqual(window, 86400)

        limit, window = _parse_rate(42, default_limit=10, default_window=120)
        self.assertEqual(limit, 42)
        self.assertEqual(window, 120)

        # Invalid unit fallback (e.g. week is rejected to avoid misconfigurations)
        limit, window = _parse_rate("5/week", default_limit=15, default_window=60)
        self.assertEqual(limit, 15)
        self.assertEqual(window, 60)

        # Invalid string fallback
        limit, window = _parse_rate("invalid", default_limit=15, default_window=60)
        self.assertEqual(limit, 15)
        self.assertEqual(window, 60)

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Trusted Proxy & IP Resolution Tests
    # ─────────────────────────────────────────────────────────────────────────

    def test_client_ip_without_trusted_proxies(self):
        req = self.factory.get("/api/lessons/")
        req.META["REMOTE_ADDR"] = "192.168.1.100"
        req.META["HTTP_X_FORWARDED_FOR"] = "203.0.113.195, 70.41.3.18"

        # When TRUSTED_PROXY_COUNT is 0, X-Forwarded-For must NOT be trusted
        with override_settings(TRUSTED_PROXY_COUNT=0):
            ip = _get_client_ip(req)
            self.assertEqual(ip, "192.168.1.100")

    def test_client_ip_with_trusted_proxies(self):
        req = self.factory.get("/api/lessons/")
        req.META["REMOTE_ADDR"] = "10.0.0.1"
        req.META["HTTP_X_FORWARDED_FOR"] = "203.0.113.195"

        # 1 proxy hop: the proxy appends only the client address it received
        with override_settings(TRUSTED_PROXY_COUNT=1):
            ip = _get_client_ip(req)
            self.assertEqual(ip, "203.0.113.195")

    def test_client_ip_with_two_trusted_proxies(self):
        req = self.factory.get("/api/lessons/")
        req.META["REMOTE_ADDR"] = "10.0.0.1"
        req.META["HTTP_X_FORWARDED_FOR"] = "203.0.113.195, 70.41.3.18"

        # 2 proxy hops: real client is the first of the two appended addresses
        with override_settings(TRUSTED_PROXY_COUNT=2):
            ip = _get_client_ip(req)
            self.assertEqual(ip, "203.0.113.195")

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Category Determination Tests
    # ─────────────────────────────────────────────────────────────────────────

    def test_endpoint_categorization(self):
        middleware = RateLimitMiddleware(get_response=lambda r: Response("OK"))

        # Auth endpoints
        req_login = self.factory.post("/api/auth/login/")
        self.assertEqual(middleware._get_endpoint_category(req_login), "auth")

        req_signup = self.factory.post("/api/auth/signup/")
        self.assertEqual(middleware._get_endpoint_category(req_signup), "auth")

        req_v1_auth = self.factory.post("/api/v1/auth/refresh/")
        self.assertEqual(middleware._get_endpoint_category(req_v1_auth), "auth")

        req_allauth = self.factory.post("/api/v1/accounts/login/")
        self.assertEqual(middleware._get_endpoint_category(req_allauth), "auth")

        req_oauth = self.factory.get("/oauth/authorize/")
        self.assertEqual(middleware._get_endpoint_category(req_oauth), "auth")

        # API reads
        req_get = self.factory.get("/api/lessons/")
        self.assertEqual(middleware._get_endpoint_category(req_get), "read")

        req_head = self.factory.head("/api/lessons/")
        self.assertEqual(middleware._get_endpoint_category(req_head), "read")

        req_options = self.factory.options("/api/lessons/")
        self.assertEqual(middleware._get_endpoint_category(req_options), "read")

        # API writes
        req_post = self.factory.post("/api/notes/")
        self.assertEqual(middleware._get_endpoint_category(req_post), "write")

        req_put = self.factory.put("/api/notes/1/")
        self.assertEqual(middleware._get_endpoint_category(req_put), "write")

        req_patch = self.factory.patch("/api/notes/1/")
        self.assertEqual(middleware._get_endpoint_category(req_patch), "write")

        req_delete = self.factory.delete("/api/notes/1/")
        self.assertEqual(middleware._get_endpoint_category(req_delete), "write")

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Auth Endpoint Limit: 5 req/min
    # ─────────────────────────────────────────────────────────────────────────

    def test_auth_endpoint_limit_enforcement(self):
        middleware = RateLimitMiddleware(get_response=lambda r: Response("OK"))

        # Fire 5 requests to /api/auth/login/
        for i in range(5):
            req = self.factory.post("/api/auth/login/")
            req.META["REMOTE_ADDR"] = "198.51.100.1"
            res = middleware.process_request(req)
            self.assertIsNone(res, f"Request {i+1} should be allowed")

        # 6th request must be throttled with HTTP 429
        req_blocked = self.factory.post("/api/auth/login/")
        req_blocked.META["REMOTE_ADDR"] = "198.51.100.1"
        res_blocked = middleware.process_request(req_blocked)

        self.assertIsNotNone(res_blocked)
        self.assertEqual(res_blocked.status_code, 429)
        self.assertEqual(res_blocked["X-RateLimit-Limit"], "5")
        self.assertEqual(res_blocked["X-RateLimit-Remaining"], "0")
        self.assertIn("Retry-After", res_blocked)
        self.assertIn("X-RateLimit-Reset", res_blocked)
        self.assertEqual(res_blocked["X-RateLimit-Category"], "auth")

        # Verify response body structure
        self.assertEqual(res_blocked.data["error"], "rate_limited")
        self.assertEqual(res_blocked.data["code"], "rate_limited")
        self.assertIn("retry_after", res_blocked.data)

    # ─────────────────────────────────────────────────────────────────────────
    # 5. API Read Limit: 60 req/min
    # ─────────────────────────────────────────────────────────────────────────

    def test_api_read_limit_enforcement(self):
        middleware = RateLimitMiddleware(get_response=lambda r: Response("OK"))

        # Fire 60 GET requests to /api/lessons/
        for i in range(60):
            req = self.factory.get("/api/lessons/")
            req.META["REMOTE_ADDR"] = "198.51.100.2"
            res = middleware.process_request(req)
            self.assertIsNone(res, f"Read request {i+1} should be allowed")

        # 61st read request should be blocked
        req_blocked = self.factory.get("/api/lessons/")
        req_blocked.META["REMOTE_ADDR"] = "198.51.100.2"
        res_blocked = middleware.process_request(req_blocked)

        self.assertIsNotNone(res_blocked)
        self.assertEqual(res_blocked.status_code, 429)
        self.assertEqual(res_blocked["X-RateLimit-Limit"], "60")
        self.assertEqual(res_blocked["X-RateLimit-Remaining"], "0")
        self.assertEqual(res_blocked["X-RateLimit-Category"], "read")

    # ─────────────────────────────────────────────────────────────────────────
    # 6. API Write Limit: 20 req/min
    # ─────────────────────────────────────────────────────────────────────────

    def test_api_write_limit_enforcement(self):
        middleware = RateLimitMiddleware(get_response=lambda r: Response("OK"))

        # Fire 20 POST requests to /api/notes/
        for i in range(20):
            req = self.factory.post("/api/notes/")
            req.META["REMOTE_ADDR"] = "198.51.100.3"
            res = middleware.process_request(req)
            self.assertIsNone(res, f"Write request {i+1} should be allowed")

        # 21st write request should be blocked
        req_blocked = self.factory.post("/api/notes/")
        req_blocked.META["REMOTE_ADDR"] = "198.51.100.3"
        res_blocked = middleware.process_request(req_blocked)

        self.assertIsNotNone(res_blocked)
        self.assertEqual(res_blocked.status_code, 429)
        self.assertEqual(res_blocked["X-RateLimit-Limit"], "20")
        self.assertEqual(res_blocked["X-RateLimit-Remaining"], "0")
        self.assertEqual(res_blocked["X-RateLimit-Category"], "write")

    # ─────────────────────────────────────────────────────────────────────────
    # 7. Client Isolation Tests (IP vs IP, User vs User, User vs IP)
    # ─────────────────────────────────────────────────────────────────────────

    def test_anonymous_client_ip_isolation(self):
        middleware = RateLimitMiddleware(get_response=lambda r: Response("OK"))

        # Exhaust auth limit for IP 1
        for _ in range(5):
            req = self.factory.post("/api/auth/login/")
            req.META["REMOTE_ADDR"] = "1.1.1.1"
            middleware.process_request(req)

        # IP 1 is blocked
        req1 = self.factory.post("/api/auth/login/")
        req1.META["REMOTE_ADDR"] = "1.1.1.1"
        self.assertEqual(middleware.process_request(req1).status_code, 429)

        # IP 2 should NOT be blocked
        req2 = self.factory.post("/api/auth/login/")
        req2.META["REMOTE_ADDR"] = "2.2.2.2"
        self.assertIsNone(middleware.process_request(req2))

    def test_authenticated_user_isolation(self):
        middleware = RateLimitMiddleware(get_response=lambda r: Response("OK"))

        # Exhaust write limit for User 1
        for _ in range(20):
            req = self.factory.post("/api/notes/")
            req.user = self.user1
            middleware.process_request(req)

        # User 1 is blocked
        req1 = self.factory.post("/api/notes/")
        req1.user = self.user1
        self.assertEqual(middleware.process_request(req1).status_code, 429)

        # User 2 should NOT be blocked
        req2 = self.factory.post("/api/notes/")
        req2.user = self.user2
        self.assertIsNone(middleware.process_request(req2))

    def test_authenticated_user_isolated_from_anonymous_ip(self):
        middleware = RateLimitMiddleware(get_response=lambda r: Response("OK"))

        # Exhaust write limit from an IP anonymously
        for _ in range(20):
            req = self.factory.post("/api/notes/")
            req.META["REMOTE_ADDR"] = "5.5.5.5"
            middleware.process_request(req)

        # Anonymous on IP 5.5.5.5 is blocked
        req_anon = self.factory.post("/api/notes/")
        req_anon.META["REMOTE_ADDR"] = "5.5.5.5"
        self.assertEqual(middleware.process_request(req_anon).status_code, 429)

        # Authenticated user on the same IP is NOT blocked
        req_auth = self.factory.post("/api/notes/")
        req_auth.META["REMOTE_ADDR"] = "5.5.5.5"
        req_auth.user = self.user1
        self.assertIsNone(middleware.process_request(req_auth))

    def test_jwt_authenticated_user_isolation(self):
        middleware = RateLimitMiddleware(get_response=lambda r: Response("OK"))
        token1 = RefreshToken.for_user(self.user1)
        token2 = RefreshToken.for_user(self.user2)

        # Exhaust write limit (20) for user1 using JWT Bearer token
        for i in range(20):
            req = self.factory.post(
                "/api/notes/",
                HTTP_AUTHORIZATION=f"Bearer {token1.access_token}",
            )
            req.META["REMOTE_ADDR"] = "3.3.3.3"
            res = middleware.process_request(req)
            self.assertIsNone(res, f"JWT write request {i+1} should be allowed")

        # 21st request for user1 is throttled
        req_blocked = self.factory.post(
            "/api/notes/",
            HTTP_AUTHORIZATION=f"Bearer {token1.access_token}",
        )
        req_blocked.META["REMOTE_ADDR"] = "3.3.3.3"
        res_blocked = middleware.process_request(req_blocked)
        self.assertIsNotNone(res_blocked)
        self.assertEqual(res_blocked.status_code, 429)

        # User 2 using different JWT on same IP is NOT throttled
        req_user2 = self.factory.post(
            "/api/notes/",
            HTTP_AUTHORIZATION=f"Bearer {token2.access_token}",
        )
        req_user2.META["REMOTE_ADDR"] = "3.3.3.3"
        self.assertIsNone(middleware.process_request(req_user2))

        # Anonymous user on same IP is NOT throttled (separate IP bucket)
        req_anon = self.factory.post("/api/notes/")
        req_anon.META["REMOTE_ADDR"] = "3.3.3.3"
        self.assertIsNone(middleware.process_request(req_anon))

    # ─────────────────────────────────────────────────────────────────────────
    # 8. Premium User Rate Multiplier
    # ─────────────────────────────────────────────────────────────────────────

    def test_premium_user_elevated_category_limits(self):
        middleware = RateLimitMiddleware(get_response=lambda r: Response("OK"))

        # Regular user write limit is 20
        # Premium user write limit is 20 * 5 = 100
        for i in range(100):
            req = self.factory.post("/api/notes/")
            req.user = self.premium_user
            res = middleware.process_request(req)
            self.assertIsNone(res, f"Premium user request {i+1} should be allowed")

        # Request 101 must be throttled with HTTP 429
        req_blocked = self.factory.post("/api/notes/")
        req_blocked.user = self.premium_user
        res_blocked = middleware.process_request(req_blocked)
        self.assertIsNotNone(res_blocked)
        self.assertEqual(res_blocked.status_code, 429)
        self.assertEqual(res_blocked["X-RateLimit-Limit"], "100")

    # ─────────────────────────────────────────────────────────────────────────
    # 9. Bypass Paths & Disable Setting
    # ─────────────────────────────────────────────────────────────────────────

    def test_bypassed_paths_never_throttled(self):
        middleware = RateLimitMiddleware(get_response=lambda r: Response("OK"))

        bypassed_urls = [
            "/health/",
            "/health/live/",
            "/health/ready/",
            "/admin/",
            "/admin/login/",
            "/static/css/main.css",
            "/media/avatars/user.jpg",
            "/api/webhooks/stripe/",
        ]

        for url in bypassed_urls:
            req = self.factory.get(url)
            req.META["REMOTE_ADDR"] = "9.9.9.9"
            for _ in range(100):
                res = middleware.process_request(req)
                self.assertIsNone(res, f"{url} must bypass rate limiting")

    def test_disable_rate_limiting_setting(self):
        middleware = RateLimitMiddleware(get_response=lambda r: Response("OK"))

        with override_settings(DISABLE_RATE_LIMITING=True):
            req = self.factory.post("/api/auth/login/")
            req.META["REMOTE_ADDR"] = "8.8.8.8"
            for _ in range(20):
                res = middleware.process_request(req)
                self.assertIsNone(res, "When disabled, requests must not be throttled")

    # ─────────────────────────────────────────────────────────────────────────
    # 10. Redis Failover & Resiliency
    # ─────────────────────────────────────────────────────────────────────────

    def test_redis_failure_falls_back_to_cache(self):
        middleware = RateLimitMiddleware(get_response=lambda r: Response("OK"))
        mock_redis = mock.MagicMock()
        mock_redis.evalsha.side_effect = redis.exceptions.ConnectionError("Redis down")
        mock_redis.script_load.side_effect = redis.exceptions.ConnectionError(
            "Redis down"
        )
        middleware.redis_client = mock_redis

        with override_settings(RATE_LIMIT_BACKEND="redis"):
            # First 5 auth requests should pass via Django cache fallback
            for i in range(5):
                req = self.factory.post("/api/auth/login/")
                req.META["REMOTE_ADDR"] = "7.7.7.7"
                res = middleware.process_request(req)
                self.assertIsNone(res)

            # 6th request is throttled
            req_blocked = self.factory.post("/api/auth/login/")
            req_blocked.META["REMOTE_ADDR"] = "7.7.7.7"
            res_blocked = middleware.process_request(req_blocked)
            self.assertEqual(res_blocked.status_code, 429)

    def test_complete_cache_failure_fails_open(self):
        middleware = RateLimitMiddleware(get_response=lambda r: Response("OK"))
        middleware.redis_client = None

        with mock.patch(
            "apps.core.middleware.ratelimit.cache.get",
            side_effect=CacheKeyWarning("Cache down"),
        ):
            req = self.factory.get("/api/lessons/")
            req.META["REMOTE_ADDR"] = "6.6.6.6"
            # Should fail open without raising an unhandled exception
            res = middleware.process_request(req)
            self.assertIsNone(res)
