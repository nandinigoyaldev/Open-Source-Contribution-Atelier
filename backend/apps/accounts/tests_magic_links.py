from unittest.mock import patch

import pytest
from apps.accounts.models import MagicLinkToken
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def test_user():
    return User.objects.create_user(
        username="testuser", email="test@example.com", password="TestPassword123!"
    )


@pytest.mark.django_db
class TestMagicLink:
    def test_magic_link_request_success(self, api_client, test_user):
        url = reverse("magic-link-request")
        with patch("apps.accounts.tasks.send_magic_link_email_task.delay") as mock_task:
            response = api_client.post(url, {"email": test_user.email})
            assert response.status_code == status.HTTP_200_OK
            assert "magic login link has been sent" in response.data["message"]

            # Verify token created
            assert MagicLinkToken.objects.filter(user=test_user, is_used=False).exists()
            mock_task.assert_called_once()

    def test_magic_link_request_nonexistent_email(self, api_client):
        url = reverse("magic-link-request")
        with patch("apps.accounts.tasks.send_magic_link_email_task.delay") as mock_task:
            response = api_client.post(url, {"email": "nobody@example.com"})
            assert response.status_code == status.HTTP_200_OK
            mock_task.assert_not_called()

    def test_magic_link_verify_success(self, api_client, test_user):
        # Create token
        token = MagicLinkToken.objects.create(user=test_user)

        url = reverse("magic-link-verify")
        response = api_client.post(url, {"token": str(token.token)})

        assert response.status_code == status.HTTP_200_OK
        assert "refresh" in response.data
        assert "access" in response.data

        # Verify token is used
        token.refresh_from_db()
        assert token.is_used == True

    def test_magic_link_verify_invalid_token(self, api_client):
        import uuid

        url = reverse("magic-link-verify")
        response = api_client.post(url, {"token": str(uuid.uuid4())})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"] == "invalid_token"

    def test_magic_link_verify_used_token(self, api_client, test_user):
        token = MagicLinkToken.objects.create(user=test_user, is_used=True)
        url = reverse("magic-link-verify")
        response = api_client.post(url, {"token": str(token.token)})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"] == "invalid_token"

    def test_magic_link_verify_expired_token(self, api_client, test_user):
        token = MagicLinkToken.objects.create(user=test_user)

        with patch("apps.accounts.models.MagicLinkToken.is_expired", return_value=True):
            url = reverse("magic-link-verify")
            response = api_client.post(url, {"token": str(token.token)})

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert response.data["error"] == "expired_token"
