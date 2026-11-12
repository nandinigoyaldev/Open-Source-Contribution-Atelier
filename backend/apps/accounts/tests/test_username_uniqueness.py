from unittest.mock import Mock, patch

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()
from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.serializers import SignupSerializer


@pytest.mark.django_db
def test_signup_rejects_case_insensitive_duplicate_username():
    User.objects.create_user(
        username="ExistingUser",
        email="existing@example.com",
        password="StrongPass1!",
    )

    serializer = SignupSerializer(
        data={
            "username": "existinguser",
            "email": "new@example.com",
            "password": "StrongPass1!",
        }
    )

    assert serializer.is_valid() is False
    assert serializer.errors["username"][0] == "Username is already taken."


from django.db import IntegrityError, connection, transaction


@pytest.mark.django_db
@pytest.mark.skipif(
    connection.vendor == "sqlite",
    reason="SQLite does not enforce case-insensitive UNIQUE indexes.",
)
def test_database_rejects_case_insensitive_duplicate_username():
    User.objects.create_user(
        username="DatabaseUser",
        email="database@example.com",
        password="StrongPass1!",
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            User.objects.create_user(
                username="databaseuser",
                email="database-two@example.com",
                password="StrongPass1!",
            )


@pytest.mark.django_db
@patch("apps.accounts.views.http_requests.get")
@patch("apps.accounts.views.http_requests.post")
def test_github_callback_derives_free_username_when_taken(
    mock_post,
    mock_get,
    settings,
):
    """A GitHub login whose preferred username is taken still signs the user
    up under a derived free username instead of failing with HTTP 400."""
    settings.CORS_ALLOWED_ORIGINS = ["http://localhost:5173"]
    settings.GITHUB_CLIENT_ID = "client-id"
    settings.GITHUB_CLIENT_SECRET = "client-secret"

    User.objects.create_user(
        username="github-user",
        email="owner@example.com",
        password="StrongPass1!",
    )

    token_response = Mock()
    token_response.raise_for_status.return_value = None
    token_response.json.return_value = {"access_token": "github-token"}
    mock_post.return_value = token_response

    github_user_response = Mock()
    github_user_response.raise_for_status.return_value = None
    github_user_response.json.return_value = {
        "login": "github-user",
        "email": "different@example.com",
    }
    mock_get.return_value = github_user_response

    client = APIClient()
    session = client.session
    session["github_oauth_state"] = {
        "value": "test-state",
        "created_at": __import__("time").time(),
    }
    session["github_oauth_verifier"] = "test-verifier"
    session.save()

    response = client.get("/api/auth/github/callback/?code=test-code&state=test-state")

    assert response.status_code == status.HTTP_302_FOUND
    created = User.objects.get(email="different@example.com")
    # Preferred name "github-user" is owned by someone else → derived instead.
    assert created.username != "github-user"
    assert User.objects.filter(username=created.username).count() == 1
    # The original owner's account is untouched.
    assert User.objects.filter(email="owner@example.com").exists()


@pytest.mark.django_db
@patch("apps.accounts.views.http_requests.get")
@patch("apps.accounts.views.http_requests.post")
def test_github_callback_allows_existing_email_owner(
    mock_post,
    mock_get,
    settings,
):
    settings.CORS_ALLOWED_ORIGINS = ["http://localhost:5173"]

    user = User.objects.create_user(
        username="github-user",
        email="same@example.com",
        password="StrongPass1!",
    )

    token_response = Mock()
    token_response.raise_for_status.return_value = None
    token_response.json.return_value = {"access_token": "github-token"}
    mock_post.return_value = token_response

    github_user_response = Mock()
    github_user_response.raise_for_status.return_value = None
    github_user_response.json.return_value = {
        "login": "github-user",
        "email": "same@example.com",
    }
    mock_get.return_value = github_user_response

    client = APIClient()
    session = client.session
    session["github_oauth_state"] = {
        "value": "test-state",
        "created_at": __import__("time").time(),
    }
    session["github_oauth_verifier"] = "test-verifier"
    session.save()

    with patch.dict(
        "os.environ",
        {
            "GITHUB_CLIENT_ID": "client-id",
            "GITHUB_CLIENT_SECRET": "client-secret",
        },
    ):
        response = client.get("/api/auth/github/callback/?code=test-code&state=test-state")

    assert response.status_code == status.HTTP_302_FOUND
    assert User.objects.filter(pk=user.pk).exists()
    assert User.objects.filter(email__iexact="same@example.com").count() == 1
