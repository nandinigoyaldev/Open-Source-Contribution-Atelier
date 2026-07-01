from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()
SANDBOX_URL = "/api/challenges/sandbox/execute/"


class SandboxThrottleTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="testuser", password="password")

    def test_anonymous_throttle(self):
        """Ensure anonymous users are throttled after 10 requests."""
        for _ in range(10):
            response = self.client.post(
                SANDBOX_URL, {"code": "print(1)"}, format="json"
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.post(SANDBOX_URL, {"code": "print(1)"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_authenticated_throttle(self):
        """Ensure authenticated users are also throttled after 10 requests."""
        self.client.force_authenticate(user=self.user)
        for _ in range(10):
            response = self.client.post(
                SANDBOX_URL, {"code": "print(1)"}, format="json"
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.post(SANDBOX_URL, {"code": "print(1)"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
