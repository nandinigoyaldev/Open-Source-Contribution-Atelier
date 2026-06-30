from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class ThrottlingTests(APITestCase):
    def test_login_throttle_limit(self):
        url = reverse("login")  # Replace with your actual login URL name

        # 5 attempts allowed (as per your settings.py: "auth_login": "5/minute")
        for _ in range(5):
            response = self.client.post(
                url, {"username": "test", "password": "password"}
            )
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # The 6th attempt should be throttled
        response = self.client.post(url, {"username": "test", "password": "password"})
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
