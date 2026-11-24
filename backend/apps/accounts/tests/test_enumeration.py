"""
Unit tests for rate-limited sliding window anti-enumeration protection on
password reset and username check endpoints (Issue #3550).
"""

import time
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()

PASSWORD_RESET_URL = "/api/auth/password-reset/"
ACCOUNTS_PASSWORD_RESET_URL = "/api/accounts/password-reset/"
CHECK_USERNAME_AUTH_URL = "/api/auth/check-username/"
CHECK_USERNAME_ACCOUNTS_URL = "/api/accounts/check-username/"


@pytest.fixture(autouse=True)
def clean_throttle_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def mock_views_async_task(monkeypatch):
    """
    Mock async_task in views to avoid connecting to background broker/Redis during unit tests.
    """
    monkeypatch.setattr("apps.accounts.views.async_task", lambda *args, **kwargs: None)
    monkeypatch.setattr("apps.core.throttling.get_redis_connection", lambda: None)


@pytest.fixture
def existing_user(db):
    return User.objects.create_user(
        username="existing_student",
        email="student@university.edu",
        password="SecureStudentPass123!",
    )


def client_with_ip(ip: str = "203.0.113.100") -> APIClient:
    client = APIClient()
    client.defaults["REMOTE_ADDR"] = ip
    return client


@pytest.mark.django_db
class TestPasswordResetAntiEnumeration:
    def test_known_and_unknown_email_identical_response(self, existing_user):
        """
        Verify that querying an existing vs non-existing email produces the exact
        same status code and payload structure, preventing user enumeration.
        """
        client = client_with_ip("203.0.113.101")
        resp_known = client.post(
            PASSWORD_RESET_URL,
            {"email": existing_user.email},
            format="json",
        )

        resp_unknown = client_with_ip("203.0.113.102").post(
            PASSWORD_RESET_URL,
            {"email": "unregistered_student@university.edu"},
            format="json",
        )

        assert resp_known.status_code == status.HTTP_200_OK
        assert resp_unknown.status_code == status.HTTP_200_OK
        assert resp_known.json() == resp_unknown.json()
        assert (
            resp_known.json()["message"]
            == "If an account with that email exists, a password reset link has been sent."
        )

    def test_accounts_alias_url_works_identically(self, existing_user):
        """
        Verify that /api/accounts/password-reset/ also works as expected.
        """
        client = client_with_ip("203.0.113.103")
        response = client.post(
            ACCOUNTS_PASSWORD_RESET_URL,
            {"email": existing_user.email},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "password reset link has been sent" in response.json()["message"]

    def test_timing_consistency_between_known_and_unknown_emails(self, existing_user):
        """
        Verify artificial timing jitter is active and normalizes response latency
        to prevent side-channel timing attacks.
        """
        client1 = client_with_ip("203.0.113.104")
        start = time.perf_counter()
        resp1 = client1.post(
            PASSWORD_RESET_URL,
            {"email": existing_user.email},
            format="json",
        )
        duration_known = time.perf_counter() - start

        client2 = client_with_ip("203.0.113.105")
        start = time.perf_counter()
        resp2 = client2.post(
            PASSWORD_RESET_URL,
            {"email": "nobody@university.edu"},
            format="json",
        )
        duration_unknown = time.perf_counter() - start

        assert resp1.status_code == status.HTTP_200_OK
        assert resp2.status_code == status.HTTP_200_OK
        # Jitter ensures at least ~30ms of normalization
        assert duration_known >= 0.03
        assert duration_unknown >= 0.03
        # Difference between existing and non-existing paths should remain minimal
        assert abs(duration_known - duration_unknown) < 0.2

    def test_honeypot_trap_silently_ignores_automated_bots(self, existing_user):
        """
        Verify honeypot fields silently succeed with 200 OK without queuing background tasks.
        """
        client = client_with_ip("203.0.113.106")
        with patch("apps.accounts.views.async_task") as mock_async_task:
            response = client.post(
                PASSWORD_RESET_URL,
                {
                    "email": existing_user.email,
                    "website": "http://spambot-link.com",
                    "honeypot": "malicious_bot",
                },
                format="json",
            )
            assert response.status_code == status.HTTP_200_OK
            assert (
                response.json()["message"]
                == "If an account with that email exists, a password reset link has been sent."
            )
            # Background task must NOT be dispatched for bot trapped by honeypot
            mock_async_task.assert_not_called()

    def test_sliding_window_rate_limiting_enforces_threshold(self):
        """
        Verify strict sliding-window rate limiting (3 requests allowed per IP, 4th throttled).
        """
        client = client_with_ip("203.0.113.107")
        for i in range(3):
            resp = client.post(
                PASSWORD_RESET_URL,
                {"email": f"test_user_{i}@university.edu"},
                format="json",
            )
            assert resp.status_code == status.HTTP_200_OK

        # 4th request must be throttled with 429 Too Many Requests
        resp_blocked = client.post(
            PASSWORD_RESET_URL,
            {"email": "overflow@university.edu"},
            format="json",
        )
        assert resp_blocked.status_code == status.HTTP_429_TOO_MANY_REQUESTS


@pytest.mark.django_db
class TestCheckUsernameAntiEnumeration:
    def test_available_username_returns_true(self):
        """
        Verify an unused username is reported as available.
        """
        client = client_with_ip("203.0.113.108")
        response = client.post(
            CHECK_USERNAME_AUTH_URL,
            {"username": "available_new_student"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["available"] is True
        assert data["username"] == "available_new_student"

    def test_existing_username_returns_false(self, existing_user):
        """
        Verify an existing username is reported as unavailable.
        """
        client = client_with_ip("203.0.113.109")
        response = client.post(
            CHECK_USERNAME_ACCOUNTS_URL,
            {"username": existing_user.username},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["available"] is False
        assert data["username"] == existing_user.username

    def test_case_insensitive_matching(self, existing_user):
        """
        Verify case-insensitivity on username checks.
        """
        client = client_with_ip("203.0.113.110")
        response = client.post(
            CHECK_USERNAME_AUTH_URL,
            {"username": existing_user.username.upper()},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["available"] is False

    def test_check_username_honeypot_trap(self):
        """
        Verify bot honeypot trap on username check endpoint.
        """
        client = client_with_ip("203.0.113.111")
        response = client.post(
            CHECK_USERNAME_AUTH_URL,
            {
                "username": "totally_fresh_username",
                "website": "https://automated-harvester.com",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        # Honeypot trap marks as unavailable to dissuade automated scrapers
        assert response.json()["available"] is False

    def test_check_username_rate_limiting_enforced(self):
        """
        Verify sliding-window rate limiting on check-username endpoint (3 allowed per IP, 4th throttled).
        """
        client = client_with_ip("203.0.113.112")
        for i in range(3):
            resp = client.post(
                CHECK_USERNAME_AUTH_URL,
                {"username": f"unique_candidate_{i}"},
                format="json",
            )
            assert resp.status_code == status.HTTP_200_OK

        resp_throttled = client.post(
            CHECK_USERNAME_AUTH_URL,
            {"username": "candidate_four"},
            format="json",
        )
        assert resp_throttled.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_check_username_timing_consistency(self, existing_user):
        """
        Verify timing jitter is present and normalizes response latency across lookups.
        """
        client1 = client_with_ip("203.0.113.113")
        start = time.perf_counter()
        resp1 = client1.post(
            CHECK_USERNAME_AUTH_URL,
            {"username": existing_user.username},
            format="json",
        )
        duration_taken = time.perf_counter() - start

        client2 = client_with_ip("203.0.113.114")
        start = time.perf_counter()
        resp2 = client2.post(
            CHECK_USERNAME_AUTH_URL,
            {"username": "unregistered_name_candidate"},
            format="json",
        )
        duration_available = time.perf_counter() - start

        assert resp1.status_code == status.HTTP_200_OK
        assert resp2.status_code == status.HTTP_200_OK
        assert duration_taken >= 0.03
        assert duration_available >= 0.03
        assert abs(duration_taken - duration_available) < 0.2
