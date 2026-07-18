from unittest.mock import Mock, patch

import pytest
from django.contrib.auth.models import User
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


@pytest.mark.django_db
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
def test_github_callback_returns_400_when_username_is_taken(
    mock_post,
    mock_get,
    settings,
):
    settings.CORS_ALLOWED_ORIGINS = ["http://localhost:5173"]

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

    with patch.dict(
        "os.environ",
        {
            "GITHUB_CLIENT_ID": "client-id",
            "GITHUB_CLIENT_SECRET": "client-secret",
        },
    ):
        response = client.get("/api/auth/github/callback/?code=test-code")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data == {"detail": "Username is already taken."}
    assert User.objects.filter(email="different@example.com").exists() is False


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

    with patch.dict(
        "os.environ",
        {
            "GITHUB_CLIENT_ID": "client-id",
            "GITHUB_CLIENT_SECRET": "client-secret",
        },
    ):
        response = client.get("/api/auth/github/callback/?code=test-code")

    assert response.status_code == status.HTTP_302_FOUND
    assert User.objects.filter(pk=user.pk).exists()
    assert User.objects.filter(email__iexact="same@example.com").count() == 1
