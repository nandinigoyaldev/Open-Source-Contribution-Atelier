from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

import pytest
import requests
from django.contrib.auth import get_user_model

User = get_user_model()
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.content.models import Lesson
from apps.progress.models import LessonProgress


class UserProfileUpdateTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="old@example.com",
            password="OldPass123!",
        )
        self.client.force_authenticate(user=self.user)

    def test_profile_update(self):
        url = "/api/auth/me/"
        payload = {
            "email": "new@example.com",
            "password": "NewPass456!",
        }

        response = self.client.put(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "new@example.com")
        self.assertTrue(self.user.check_password("NewPass456!"))


@pytest.mark.django_db
def test_signup_and_login_flow():
    client = APIClient()
    signup_response = client.post(
        "/api/auth/signup/",
        {
            "username": "mentor",
            "email": "mentor@example.com",
            "password": "Strongpass123!",
        },
        format="json",
    )
    assert signup_response.status_code == 201

    login_response = client.post(
        "/api/auth/login/",
        {"username": "mentor", "password": "Strongpass123!"},
        format="json",
    )
    assert login_response.status_code == 200
    assert "access" in login_response.data


@pytest.mark.django_db
def test_refresh_token_returns_valid_access_token():
    client = APIClient()

    User.objects.create_user(
        username="refresh_user",
        email="refresh@example.com",
        password="StrongPass123!",
    )

    login_response = client.post(
        "/api/auth/login/",
        {
            "username": "refresh_user",
            "password": "StrongPass123!",
        },
        format="json",
    )

    assert login_response.status_code == 200
    assert "refresh" in login_response.data

    refresh_response = client.post(
        "/api/auth/refresh/",
        {"refresh": login_response.data["refresh"]},
        format="json",
    )

    assert refresh_response.status_code == 200
    assert "access" in refresh_response.data
    assert isinstance(refresh_response.data["access"], str)
    assert len(refresh_response.data["access"]) > 0
    assert refresh_response.data["access"].strip() != ""


@pytest.mark.django_db
def test_signup_saves_email_as_lowercase():
    client = APIClient()

    response = client.post(
        "/api/auth/signup/",
        {
            "username": "mentor_lowercase",
            "email": "MENTOR@EXAMPLE.COM",
            "password": "Strongpass123!",
        },
        format="json",
    )

    assert response.status_code == 201

    user = User.objects.get(username="mentor_lowercase")
    assert user.email == "mentor@example.com"


@pytest.mark.django_db
def test_login_with_email_identifier():
    client = APIClient()
    User.objects.create_user(
        username="mentor_email_login",
        email="mentor-email@example.com",
        password="strongpass123",
    )

    login_response = client.post(
        "/api/auth/login/",
        {"username": "mentor-email@example.com", "password": "strongpass123"},
        format="json",
    )

    assert login_response.status_code == 200
    assert "access" in login_response.data


@pytest.mark.django_db
@patch("apps.accounts.views.http_requests.get")
def test_google_login_creates_user_and_returnss(mock_get):
    client = APIClient()

    mock_resp = Mock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"email": "google-user@example.com"}
    mock_get.return_value = mock_resp

    response = client.post(
        "/api/auth/google/",
        {"access_token": "fake"},
        format="json",
    )

    assert response.status_code == 200
    assert "access" in response.data
    assert User.objects.filter(email="google-user@example.com").exists()


@pytest.mark.django_db
@patch("apps.accounts.views.http_requests.get")
def test_google_login_with_id_token_fallback(mock_get):
    client = APIClient()

    # First call (userinfo) fails, second call (tokeninfo) succeeds
    fail_resp = Mock()
    fail_resp.ok = False

    success_resp = Mock()
    success_resp.ok = True
    success_resp.json.return_value = {"email": "google-idtoken@example.com"}

    mock_get.side_effect = [fail_resp, success_resp]

    response = client.post(
        "/api/auth/google/",
        {"id_token": "header.payload.signature"},
        format="json",
    )

    assert response.status_code == 200
    assert "access" in response.data
    assert User.objects.filter(email="google-idtoken@example.com").exists()


@pytest.mark.django_db
def test_google_login_missing_token_returns_400():
    client = APIClient()
    response = client.post("/api/auth/google/", {}, format="json")
    assert response.status_code == 400
    assert response.data["detail"] == "No access token provided"


@pytest.mark.django_db
@patch("apps.accounts.views.http_requests.get")
def test_google_login_invalid_token_returns_401(mock_get):
    client = APIClient()

    fail_resp = Mock()
    fail_resp.ok = False
    mock_get.return_value = fail_resp

    response = client.post(
        "/api/auth/google/",
        {"access_token": "invalid-token"},
        format="json",
    )

    assert response.status_code == 401
    assert response.data["detail"] == "Failed to verify Google token"


@pytest.mark.django_db
@patch("apps.accounts.views.http_requests.get")
def test_google_login_audience_mismatch_returns_401(mock_get, settings):
    settings.GOOGLE_CLIENT_ID = "expected-client.apps.googleusercontent.com"
    client = APIClient()

    tokeninfo = Mock()
    tokeninfo.ok = True
    tokeninfo.json.return_value = {
        "aud": "different-client.apps.googleusercontent.com",
        "email": "user@example.com",
        "email_verified": True,
    }
    mock_get.return_value = tokeninfo

    response = client.post(
        "/api/auth/google/",
        {"id_token": "header.payload.signature"},
        format="json",
    )

    assert response.status_code == 401
    assert response.data["code"] == "google_audience_mismatch"


@pytest.mark.django_db
@patch("apps.accounts.views.http_requests.get")
def test_google_login_unverified_email_returns_401(mock_get, settings):
    settings.DEBUG = False
    settings.GOOGLE_CLIENT_ID = "expected-client.apps.googleusercontent.com"
    client = APIClient()

    userinfo = Mock()
    userinfo.ok = True
    userinfo.json.return_value = {
        "email": "user@example.com",
        "email_verified": False,
    }
    mock_get.return_value = userinfo

    response = client.post(
        "/api/auth/google/",
        {"access_token": "some-access-token"},
        format="json",
    )

    assert response.status_code == 401
    assert response.data["code"] == "google_email_unverified"


@pytest.mark.django_db
def test_google_login_auth_code_missing_secret_returns_501(settings):
    settings.GOOGLE_CLIENT_SECRET = ""
    client = APIClient()

    response = client.post(
        "/api/auth/google/",
        {"code": "auth-code-123"},
        format="json",
    )

    assert response.status_code == 501
    assert response.data["code"] == "google_oauth_not_configured"


@pytest.mark.django_db
@patch("apps.accounts.views.http_requests.post")
def test_google_login_auth_code_exchange_unreachable_returns_502(mock_post, settings):
    settings.GOOGLE_CLIENT_SECRET = "client-secret"
    client = APIClient()

    mock_post.side_effect = requests.RequestException("network down")

    response = client.post(
        "/api/auth/google/",
        {"code": "auth-code-123"},
        format="json",
    )

    assert response.status_code == 502
    assert response.data["code"] == "google_unreachable"


@pytest.mark.django_db
@patch("apps.accounts.views.http_requests.post")
def test_google_login_auth_code_exchange_rejected_returns_401(mock_post, settings):
    settings.GOOGLE_CLIENT_SECRET = "client-secret"
    client = APIClient()

    rejected = Mock()
    rejected.ok = False
    rejected.status_code = 400
    mock_post.return_value = rejected

    response = client.post(
        "/api/auth/google/",
        {"code": "auth-code-123"},
        format="json",
    )

    assert response.status_code == 401
    assert response.data["code"] == "google_code_rejected"


@pytest.mark.django_db
@patch("apps.accounts.views.http_requests.post")
@patch("apps.accounts.views.http_requests.get")
def test_google_login_auth_code_flow_creates_user(mock_get, mock_post, settings):
    settings.GOOGLE_CLIENT_SECRET = "client-secret"
    settings.GOOGLE_CLIENT_ID = "expected-client.apps.googleusercontent.com"
    client = APIClient()

    token_resp = Mock()
    token_resp.ok = True
    token_resp.json.return_value = {
        "id_token": "issued-id-token",
        "access_token": "issued-access-token",
    }
    mock_post.return_value = token_resp

    tokeninfo = Mock()
    tokeninfo.ok = True
    tokeninfo.json.return_value = {
        "aud": "expected-client.apps.googleusercontent.com",
        "email": "code-user@example.com",
        "email_verified": True,
    }
    mock_get.return_value = tokeninfo

    response = client.post(
        "/api/auth/google/",
        {"code": "auth-code-123", "redirect_uri": "http://localhost:5173"},
        format="json",
    )

    assert response.status_code == 200
    assert "access" in response.data
    assert User.objects.filter(email="code-user@example.com").exists()


@pytest.mark.django_db
def test_github_oauth_start_redirects_to_github(monkeypatch):
    client = APIClient()
    monkeypatch.setenv("GITHUB_CLIENT_ID", "github-client-id")

    response = client.get("/api/auth/github/")

    assert response.status_code == 302
    assert response["Location"].startswith("https://github.com/login/oauth/authorize?")
    assert "client_id=github-client-id" in response["Location"]
    assert (
        "redirect_uri=http%3A%2F%2Ftestserver%2Fapi%2Fauth%2Fgithub%2Fcallback%2F"
        in response["Location"]
    )


@pytest.mark.django_db
@patch("apps.accounts.views.http_requests.get")
@patch("apps.accounts.views.http_requests.post")
def test_github_oauth_callback_creates_user_and_redirects_withs(
    mock_post, mock_get, monkeypatch
):
    client = APIClient()
    monkeypatch.setenv("GITHUB_CLIENT_ID", "github-client-id")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "github-client-secret")
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:5173")

    _resp = Mock()
    _resp.json.return_value = {"access_token": "github"}
    _resp.raise_for_status.return_value = None
    mock_post.return_value = _resp

    user_resp = Mock()
    user_resp.json.return_value = {"login": "octo-dev", "email": "octo@example.com"}
    user_resp.raise_for_status.return_value = None
    mock_get.return_value = user_resp

    # Drive the start endpoint first so the session carries the CSRF state
    # and PKCE verifier the callback validates.
    start = client.get("/api/auth/github/")
    assert start.status_code == 302
    state = parse_qs(urlparse(start["Location"]).query)["state"][0]

    response = client.get(f"/api/auth/github/callback/?code=fake-code&state={state}")

    assert response.status_code == 302
    assert response["Location"].startswith(
        "http://localhost:5173/auth/github/callback?"
    )
    assert "access=" in response["Location"]
    assert "refresh=" in response["Location"]
    assert User.objects.filter(email="octo@example.com").exists()


@pytest.mark.django_db
def test_sandbox_verifier_rejects_unsafe_command():
    user = User.objects.create_user(username="admin", password="strongpass123")
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        "/api/sandbox/verify/",
        {"command": "rm -rf .", "expected_command": "git status"},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["accepted"] is False


@pytest.mark.django_db
def test_me_endpoint():
    client = APIClient()

    # hitting a GET request without JWT
    anonymous_response = client.get("/api/auth/me/")
    assert anonymous_response.status_code == 401

    user = User.objects.create_user(
        username="testuser", email="testuser@example.com", password="strongpass123"
    )

    # hitting a GET request with JWT
    client.force_authenticate(user=user)
    auth_response = client.get("/api/auth/me/")

    assert auth_response.status_code == 200
    assert auth_response.data["id"] == user.id
    assert auth_response.data["username"] == "testuser"
    assert auth_response.data["email"] == "testuser@example.com"
    assert auth_response.data["is_staff"] is False


@pytest.mark.django_db
def test_progress_post_creates_dynamic_lesson_stub():
    user = User.objects.create_user(username="progress_user", password="strongpass123")

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        "/api/progress/me/",
        {
            "lesson_slug": "new-dynamic-lesson",
            "score": 100,
            "completed": True,
        },
        format="json",
    )

    assert response.status_code == 201

    lesson = Lesson.objects.get(slug="new-dynamic-lesson")

    assert lesson.title == "New Dynamic Lesson"
    assert lesson.summary == "Dynamic learning module"
    assert lesson.content == "Dynamic content loaded from local file storage."
    assert lesson.difficulty == "beginner"

    assert LessonProgress.objects.filter(user=user, lesson=lesson).exists()


@pytest.mark.django_db
def test_signup_duplicate_email_returns_400():
    """Registering with an already-used email address must return HTTP 400."""
    client = APIClient()

    # First signup – should succeed
    User.objects.create_user(
        username="existing_user",
        email="taken@example.com",
        password="AlreadyHere!9",
    )

    # Second signup with the same email – should be rejected
    response = client.post(
        "/api/auth/signup/",
        {
            "username": "new_user",
            "email": "taken@example.com",
            "password": "AnotherPass!9",
        },
        format="json",
    )

    assert response.status_code == 400
    assert "errors" in response.data
    assert "email" in response.data["errors"]
    assert "already exists" in str(response.data["errors"]["email"]).lower()


@pytest.mark.django_db
def test_signup_duplicate_email_is_case_insensitive():
    """Email uniqueness check must be case-insensitive (TAKEN@EXAMPLE.COM == taken@example.com)."""
    client = APIClient()

    User.objects.create_user(
        username="existing_user2",
        email="taken@example.com",
        password="AlreadyHere!9",
    )

    # Try to register with the same email in a different case
    response = client.post(
        "/api/auth/signup/",
        {
            "username": "new_user2",
            "email": "TAKEN@EXAMPLE.COM",
            "password": "AnotherPass!9",
        },
        format="json",
    )

    assert response.status_code == 400
    assert "errors" in response.data
    assert "email" in response.data["errors"]
