import time
from unittest import mock
from django.test import TestCase, RequestFactory
from rest_framework.views import APIView
from rest_framework.response import Response
from apps.core.throttling import SlidingWindowAnonThrottle, get_redis_connection


class TestAnonThrottle(SlidingWindowAnonThrottle):
    rate = "100/minute"


class DummyView(APIView):
    throttle_classes = [TestAnonThrottle]

    def get(self, request):
        return Response("OK")


class SlidingWindowThrottleTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.view = DummyView.as_view()
        self.redis = get_redis_connection()
        if self.redis:
            self.redis.flushdb()

    def test_burst_traffic(self):
        # We only run this if redis is available in the test env
        if not self.redis:
            self.skipTest("Redis not available")

        # 100 requests should be allowed
        for i in range(100):
            request = self.factory.get("/")
            # Use same IP for all
            request.META["REMOTE_ADDR"] = "192.168.1.1"
            response = self.view(request)
            self.assertEqual(response.status_code, 200, f"Failed on request {i}")

        # The 101st request should be throttled
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        response = self.view(request)
        self.assertEqual(response.status_code, 429)
        self.assertTrue(int(response["Retry-After"]) > 0)

    @mock.patch("time.time")
    def test_sliding_window_recovery(self, mock_time):
        if not self.redis:
            self.skipTest("Redis not available")

        mock_time.return_value = 1000.0

        # Max out the throttle
        for i in range(100):
            request = self.factory.get("/")
            request.META["REMOTE_ADDR"] = "10.0.0.1"
            response = self.view(request)
            self.assertEqual(response.status_code, 200)

        # Confirm 101st is blocked
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "10.0.0.1"
        response = self.view(request)
        self.assertEqual(response.status_code, 429)

        # Advance time by 61 seconds (past the 60 second window)
        mock_time.return_value = 1061.0

        # Should now allow requests again
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "10.0.0.1"
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
