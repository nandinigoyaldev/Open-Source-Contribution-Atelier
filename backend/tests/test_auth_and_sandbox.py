import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from unittest.mock import patch, Mock


@pytest.mark.django_db
def test_signup_and_login_flow():
    client = APIClient()
    signup_response = client.post(
        "/api/auth/signup/",
        {
            "username": "mentor",
            "email": "mentor@example.com",
            "password": "strongpass123",
        },
        format="json",
    )
    assert signup_response.status_code == 201

    login_response = client.post(
        "/api/auth/login/",
        {"username": "mentor", "password": "strongpass123"},
        format="json",
    )
    assert login_response.status_code == 200
    assert "access" in login_response.data


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
def test_google_login_creates_user_and_returns_tokens(mock_get):
    client = APIClient()

    mock_resp = Mock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"email": "google-user@example.com"}
    mock_get.return_value = mock_resp

    response = client.post(
        "/api/auth/google/",
        {"access_token": "fake-token"},
        format="json",
    )

    assert response.status_code == 200
    assert "access" in response.data
    assert User.objects.filter(email="google-user@example.com").exists()


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
def test_github_oauth_callback_creates_user_and_redirects_with_tokens(
    mock_post, mock_get, monkeypatch
):
    client = APIClient()
    monkeypatch.setenv("GITHUB_CLIENT_ID", "github-client-id")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "github-client-secret")
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:5173")

    token_resp = Mock()
    token_resp.json.return_value = {"access_token": "github-token"}
    token_resp.raise_for_status.return_value = None
    mock_post.return_value = token_resp

    user_resp = Mock()
    user_resp.json.return_value = {"login": "octo-dev", "email": "octo@example.com"}
    user_resp.raise_for_status.return_value = None
    mock_get.return_value = user_resp

    response = client.get("/api/auth/github/callback/?code=fake-code")

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
