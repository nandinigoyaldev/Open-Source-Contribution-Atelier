import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user():
    return User.objects.create_user(
        username="refresh_test_user",
        email="refresh_test@example.com",
        password="TestPassword123!",
    )


@pytest.fixture
def valid_refresh_token(user):
    return str(RefreshToken.for_user(user))


@pytest.mark.django_db
class TestTokenRefresh:
    def test_successful_access_token_refresh(self, client, valid_refresh_token):
        response = client.post(
            "/api/auth/refresh/", {"refresh": valid_refresh_token}, format="json"
        )
        assert response.status_code == 200
        assert "access" in response.data
        assert "refresh" in response.data  # Rotation is enabled
        assert response.data["refresh"] != valid_refresh_token

    def test_refresh_token_rotation_and_blacklist(self, client, valid_refresh_token):
        # First refresh
        response1 = client.post(
            "/api/auth/refresh/", {"refresh": valid_refresh_token}, format="json"
        )
        assert response1.status_code == 200
        new_refresh = response1.data["refresh"]

        # Attempt to reuse the original refresh token (should be blacklisted)
        response2 = client.post(
            "/api/auth/refresh/", {"refresh": valid_refresh_token}, format="json"
        )
        assert response2.status_code == 401
        assert response2.data["code"] == "token_not_valid"

        # The new refresh token should work
        response3 = client.post(
            "/api/auth/refresh/", {"refresh": new_refresh}, format="json"
        )
        assert response3.status_code == 200

    def test_expired_or_invalid_token(self, client):
        invalid_token = "eyJhbGciOiJIUzI1NiIsInR5cCI.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.invalid"
        response = client.post(
            "/api/auth/refresh/", {"refresh": invalid_token}, format="json"
        )
        assert response.status_code == 401
        assert response.data["code"] == "token_not_valid"

    def test_malformed_request(self, client):
        response = client.post(
            "/api/auth/refresh/", {}, format="json"  # missing 'refresh'
        )
        assert response.status_code == 400
        assert "errors" in response.data
        assert "refresh" in response.data["errors"]
