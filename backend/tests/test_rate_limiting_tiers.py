import time
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from rest_framework import status
from rest_framework.exceptions import Throttled
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.exceptions import throttle_exception_handler
from apps.core.middleware.ratelimit import RateLimitMiddleware
from apps.core.throttling import (
    HeavyOperationThrottle,
    SlidingWindowAnonThrottle,
    SlidingWindowPremiumThrottle,
    SlidingWindowUserThrottle,
    is_premium_user,
)

User = get_user_model()


class RateLimitingTierTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="normal_user", password="password"
        )
        self.premium_user = User.objects.create_user(
            username="premium_user", password="password", is_staff=True
        )

    def test_is_premium_user(self):
        self.assertFalse(is_premium_user(self.user))
        self.assertTrue(is_premium_user(self.premium_user))

    def test_sliding_window_user_throttle_tier_assignment(self):
        user_throttle = SlidingWindowUserThrottle()

        # Regular user should resolve to "user" scope
        req_regular = self.factory.get("/")
        req_regular.user = self.user
        user_throttle.allow_request(req_regular, None)
        self.assertEqual(user_throttle.scope, "user")

        # Premium user should resolve to "premium" scope
        req_premium = self.factory.get("/")
        req_premium.user = self.premium_user
        user_throttle.allow_request(req_premium, None)
        self.assertEqual(user_throttle.scope, "premium")

    def test_heavy_operation_throttle_scope(self):
        heavy_throttle = HeavyOperationThrottle()
        self.assertEqual(heavy_throttle.scope, "heavy_operation")

    def test_rate_limit_middleware_tier_headers(self):
        middleware = RateLimitMiddleware(get_response=lambda r: Response("OK"))

        # Test anonymous request headers
        req_anon = self.factory.get("/api/lessons/")
        req_anon.META["REMOTE_ADDR"] = "192.168.1.10"
        middleware.process_request(req_anon)
        response = middleware.process_response(req_anon, Response("OK"))

        # GET is also bound by the 60/minute read bucket, which is the tighter one.
        self.assertEqual(response["X-RateLimit-Limit"], "60")
        self.assertIn("X-RateLimit-Remaining", response)
        self.assertIn("X-RateLimit-Reset", response)

        # Test authenticated request headers
        req_auth = self.factory.get("/api/lessons/")
        req_auth.user = self.user
        middleware.process_request(req_auth)
        response_auth = middleware.process_response(req_auth, Response("OK"))

        self.assertEqual(response_auth["X-RateLimit-Limit"], "60")
        self.assertEqual(response_auth["X-RateLimit-Category-Limit"], "60")

        # Test premium request headers
        req_prem = self.factory.get("/api/lessons/")
        req_prem.user = self.premium_user
        middleware.process_request(req_prem)
        response_prem = middleware.process_response(req_prem, Response("OK"))

        # premium reads get 5x the category budget
        self.assertEqual(response_prem["X-RateLimit-Limit"], "300")

    def test_middleware_429_response_format(self):
        middleware = RateLimitMiddleware(get_response=lambda r: Response("OK"))
        middleware.anon_limit = 1  # Force limit of 1 for testing

        req = self.factory.get("/api/test-limit/")
        req.META["REMOTE_ADDR"] = "10.10.10.10"

        res1 = middleware.process_request(req)
        self.assertIsNone(res1)  # Request 1 allowed

        res2 = middleware.process_request(req)
        self.assertIsNotNone(res2)  # Request 2 throttled
        self.assertEqual(res2.status_code, 429)
        self.assertIn("Retry-After", res2)
        self.assertIn("X-RateLimit-Limit", res2)
        self.assertEqual(res2["X-RateLimit-Remaining"], "0")

    def test_exception_handler_throttled_response(self):
        exc = Throttled(wait=45)
        context = {}
        resp = throttle_exception_handler(exc, context)

        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(resp.data["error"], "rate_limited")
        self.assertEqual(resp.data["code"], "rate_limited")
        self.assertEqual(resp.data["retry_after"], 46)
        self.assertEqual(resp["Retry-After"], "46")
        self.assertEqual(resp["X-RateLimit-Remaining"], "0")
