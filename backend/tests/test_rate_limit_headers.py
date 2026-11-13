"""X-RateLimit-* headers on API responses (issue #3418)."""

import time
from typing import Any
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from rest_framework.exceptions import Throttled
from rest_framework.response import Response
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.exceptions import throttle_exception_handler
from apps.accounts.throttles import StrictIdentityLoginThrottle
from apps.core.middleware.ratelimit import RateLimitMiddleware
from apps.core.throttling import (
    RateLimitState,
    SlidingWindowAnonThrottle,
    get_rate_limit_states,
    most_restrictive,
    record_throttle_state,
)
from apps.events.throttles import EventListRateThrottle

User = get_user_model()

EVENTS_URL = "/api/events/events/"


def _state(limit, remaining, reset) -> RateLimitState:
    return {"limit": limit, "remaining": remaining, "reset": reset}


class MostRestrictiveTests(TestCase):
    def test_empty(self):
        self.assertIsNone(most_restrictive([]))
        self.assertIsNone(most_restrictive([None]))

    def test_lowest_remaining_wins(self):
        picked = most_restrictive(
            [_state(1000, 990, 3000), _state(60, 12, 20), _state(100, 50, 10)]
        )
        self.assertEqual(picked, _state(60, 12, 20))

    def test_tie_prefers_the_later_reset(self):
        picked = most_restrictive([_state(5, 0, 10), _state(100, 0, 90)])
        self.assertEqual(picked, _state(100, 0, 90))


class RateLimitHeaderResponseTests(TestCase):
    client: Any
    """Whole stack: middleware + DRF throttles + exception handler."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="rl_user", email="rl_user@example.com", password="pw123456x"
        )
        self.client = APIClient()
        token = RefreshToken.for_user(self.user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def tearDown(self):
        cache.clear()

    def _strict_events_limit(self, rate="3/minute"):
        rates = dict(getattr(EventListRateThrottle, "THROTTLE_RATES", None) or {})
        rates["events_list"] = rate
        return mock.patch.object(EventListRateThrottle, "THROTTLE_RATES", rates)

    def test_success_reports_category_limit_not_hourly_tier(self):
        # Authenticated tier is 1000/hour, but reads are 60/minute.
        before = int(time.time())
        res = self.client.get(EVENTS_URL)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["X-RateLimit-Limit"], "60")
        self.assertEqual(res["X-RateLimit-Remaining"], "59")
        self.assertTrue(before + 1 <= int(res["X-RateLimit-Reset"]) <= before + 61)
        self.assertNotIn("Retry-After", res)

        res = self.client.get(EVENTS_URL)
        self.assertEqual(res["X-RateLimit-Remaining"], "58")

    def test_success_reports_view_throttle_when_it_is_stricter(self):
        with self._strict_events_limit():
            remaining = []
            for _ in range(3):
                res = self.client.get(EVENTS_URL)
                self.assertEqual(res.status_code, 200)
                self.assertEqual(res["X-RateLimit-Limit"], "3")
                remaining.append(res["X-RateLimit-Remaining"])
        self.assertEqual(remaining, ["2", "1", "0"])

    def test_throttled_response_matches_the_throttle_that_refused(self):
        with self._strict_events_limit():
            for _ in range(3):
                self.assertEqual(self.client.get(EVENTS_URL).status_code, 200)
            before = int(time.time())
            res = self.client.get(EVENTS_URL)

        # Status code and body are what they were before the headers existed.
        self.assertEqual(res.status_code, 429)
        self.assertEqual(res.data["code"], "rate_limited")
        self.assertEqual(res["X-RateLimit-Limit"], "3")
        self.assertEqual(res["X-RateLimit-Remaining"], "0")
        retry_after = int(res["Retry-After"])
        self.assertTrue(1 <= retry_after <= 61)
        self.assertTrue(
            abs(int(res["X-RateLimit-Reset"]) - (before + retry_after)) <= 1
        )

    def test_middleware_429_keeps_its_headers(self):
        responses = [
            self.client.get(EVENTS_URL) for _ in range(settings_read_limit() + 1)
        ]
        res = responses[-1]
        self.assertEqual(res.status_code, 429)
        self.assertEqual(res["X-RateLimit-Limit"], str(settings_read_limit()))
        self.assertEqual(res["X-RateLimit-Remaining"], "0")
        self.assertIn("Retry-After", res)
        self.assertIn("X-RateLimit-Reset", res)

    def test_view_throttle_headers_without_the_middleware_limits(self):
        # DRF throttles still run with the middleware switched off, and the
        # headers must say what they enforced.
        with override_settings(DISABLE_RATE_LIMITING=True), self._strict_events_limit():
            res = self.client.get(EVENTS_URL)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["X-RateLimit-Limit"], "3")
        self.assertEqual(res["X-RateLimit-Remaining"], "2")

    def test_no_secrets_in_headers(self):
        res = self.client.get(EVENTS_URL)
        blob = " ".join(f"{k}: {v}" for k, v in res.items() if "ratelimit" in k.lower())
        self.assertNotIn(str(self.user.pk) + ":", blob)
        self.assertNotIn(self.user.username, blob)
        self.assertNotIn("Bearer", blob)

    def test_cors_exposes_the_headers(self):
        for name in (
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            "Retry-After",
        ):
            self.assertIn(name, settings.CORS_EXPOSE_HEADERS)


def settings_read_limit():
    return int(RateLimitMiddleware(lambda r: Response("OK")).read_limit)


class MiddlewareResetTests(TestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

    def tearDown(self):
        cache.clear()

    def _request(self):
        req = self.factory.get("/api/lessons/")
        req.META["REMOTE_ADDR"] = "203.0.113.7"
        return req

    def test_reset_counts_down_instead_of_restarting_the_window(self):
        middleware = RateLimitMiddleware(lambda r: Response("OK"))
        with (
            mock.patch("apps.core.middleware.ratelimit.time") as fake_time,
            mock.patch("apps.core.throttling.time", fake_time),
        ):
            fake_time.time.return_value = 10_000.0
            req = self._request()
            self.assertIsNone(middleware.process_request(req))
            res = middleware.process_response(req, Response("OK"))
            self.assertEqual(res["X-RateLimit-Reset"], str(10_000 + 60))

            fake_time.time.return_value = 10_045.0
            req = self._request()
            self.assertIsNone(middleware.process_request(req))
            res = middleware.process_response(req, Response("OK"))
            # Same window as the first request: it ends at 10_060, not 10_105.
            self.assertEqual(res["X-RateLimit-Reset"], str(10_060))
            self.assertEqual(res["X-RateLimit-Remaining"], "58")

    def test_429_retry_after_is_what_is_left_of_the_window(self):
        middleware = RateLimitMiddleware(lambda r: Response("OK"))
        middleware.read_limit = 1
        with mock.patch("apps.core.middleware.ratelimit.time") as fake_time:
            fake_time.time.return_value = 20_000.0
            self.assertIsNone(middleware.process_request(self._request()))
            fake_time.time.return_value = 20_050.0
            res = middleware.process_request(self._request())
        assert res is not None
        self.assertEqual(res.status_code, 429)
        self.assertEqual(res["Retry-After"], "10")
        self.assertEqual(res["X-RateLimit-Reset"], str(20_060))

    def test_view_state_and_tier_are_combined(self):
        middleware = RateLimitMiddleware(lambda r: Response("OK"))
        req = self._request()
        self.assertIsNone(middleware.process_request(req))
        # A throttle on the view with less room than the 60/minute read bucket.
        from apps.core.throttling import record_rate_limit_state

        record_rate_limit_state(req, _state(10, 4, 30))
        res = middleware.process_response(req, Response("OK"))
        assert res is not None
        self.assertEqual(res["X-RateLimit-Limit"], "10")
        self.assertEqual(res["X-RateLimit-Remaining"], "4")
        # The category headers that were already there are unchanged.
        self.assertEqual(res["X-RateLimit-Category"], "read")
        self.assertEqual(res["X-RateLimit-Category-Limit"], "60")


class ThrottleStateRecordingTests(TestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

    def _request(self):
        req = self.factory.get("/")
        req.META["REMOTE_ADDR"] = "198.51.100.9"
        setattr(req, "user", mock.Mock(is_authenticated=False))
        return req

    def test_redis_sliding_window_state(self):
        class Throttle(SlidingWindowAnonThrottle):
            rate = "5/minute"

        class FakePipeline:
            def __init__(self, count, oldest):
                self.results = [0, 1, count, True, [("m", oldest)]]

            def __getattr__(self, name):
                return lambda *a, **k: None

            def execute(self):
                return self.results

        class FakeRedis:
            def __init__(self, count, oldest):
                self.count, self.oldest = count, oldest

            def pipeline(self):
                return FakePipeline(self.count, self.oldest)

            def zrem(self, *a):
                pass

            def zrange(self, *a, **k):
                return [("m", self.oldest)]

        now = time.time()
        with mock.patch(
            "apps.core.throttling.get_redis_connection",
            return_value=FakeRedis(2, now - 20),
        ):
            req = self._request()
            self.assertTrue(Throttle().allow_request(req, None))
        (state,) = get_rate_limit_states(req)
        self.assertEqual((state["limit"], state["remaining"]), (5, 3))
        self.assertTrue(39 <= state["reset"] <= 41)

        with mock.patch(
            "apps.core.throttling.get_redis_connection",
            return_value=FakeRedis(6, now - 20),
        ):
            req = self._request()
            self.assertFalse(Throttle().allow_request(req, None))
        (state,) = get_rate_limit_states(req)
        self.assertEqual((state["limit"], state["remaining"]), (5, 0))

    def test_local_fallback_state(self):
        class Throttle(SlidingWindowAnonThrottle):
            rate = "2/minute"

        with mock.patch("apps.core.throttling.get_redis_connection", return_value=None):
            seen = []
            for _ in range(3):
                req = self._request()
                allowed = Throttle().allow_request(req, None)
                seen.append((allowed, get_rate_limit_states(req)[0]["remaining"]))
        self.assertEqual(seen, [(True, 1), (True, 0), (False, 0)])

    def test_identity_keyed_throttle_is_hidden_on_success_only(self):
        throttle = StrictIdentityLoginThrottle()
        throttle.num_requests, throttle.duration = 5, 60
        throttle.key, throttle.history = "k", [time.time()]
        req = self._request()
        record_throttle_state(req, throttle, True)
        self.assertEqual(get_rate_limit_states(req), [])
        record_throttle_state(req, throttle, False)
        self.assertEqual(len(get_rate_limit_states(req)), 1)

    def test_throttle_that_did_not_apply_records_nothing(self):
        class Throttle(SlidingWindowAnonThrottle):
            rate = "2/minute"

        req = self._request()
        # anon throttle skips authenticated users
        setattr(req, "user", mock.Mock(is_authenticated=True))
        self.assertTrue(Throttle().allow_request(req, None))
        self.assertEqual(get_rate_limit_states(req), [])


class ExceptionHandlerHeaderTests(TestCase):
    def test_hand_raised_throttled_does_not_invent_a_limit(self):
        resp = throttle_exception_handler(Throttled(wait=45), {})
        self.assertEqual(resp.status_code, 429)
        self.assertEqual(resp["Retry-After"], "46")
        self.assertEqual(resp["X-RateLimit-Remaining"], "0")
        self.assertIn("X-RateLimit-Reset", resp)
        self.assertNotIn("X-RateLimit-Limit", resp)
