import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user():
    return User.objects.create_user(
        username="tzuser", email="tzuser@example.com", password="Password123!"
    )


@pytest.mark.django_db
class TestTimezoneSetting:
    def test_default_timezone_is_utc(self, api_client, user):
        api_client.force_authenticate(user=user)
        response = api_client.get("/api/auth/me/")
        assert response.status_code == 200
        assert response.data["timezone"] == "UTC"

    def test_update_to_valid_timezone(self, api_client, user):
        api_client.force_authenticate(user=user)
        response = api_client.put(
            "/api/auth/me/",
            {"timezone": "Asia/Kolkata"},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["timezone"] == "Asia/Kolkata"

        user.refresh_from_db()
        assert user.profile.timezone == "Asia/Kolkata"

    def test_update_to_invalid_timezone_rejected(self, api_client, user):
        api_client.force_authenticate(user=user)
        response = api_client.put(
            "/api/auth/me/",
            {"timezone": "Mars/Phobos"},
            format="json",
        )
        assert response.status_code == 400
        assert "timezone" in response.data["errors"]

    def test_timezone_persists_across_requests(self, api_client, user):
        api_client.force_authenticate(user=user)
        api_client.put(
            "/api/auth/me/",
            {"timezone": "America/New_York"},
            format="json",
        )
        response = api_client.get("/api/auth/me/")
        assert response.data["timezone"] == "America/New_York"

    def test_updating_other_fields_does_not_reset_timezone(self, api_client, user):
        api_client.force_authenticate(user=user)
        api_client.put(
            "/api/auth/me/",
            {"timezone": "Europe/London"},
            format="json",
        )
        # Update email only, timezone should be untouched
        response = api_client.put(
            "/api/auth/me/",
            {"email": "newemail@example.com"},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["timezone"] == "Europe/London"

    def test_unauthenticated_request_rejected(self, api_client):
        response = api_client.put(
            "/api/auth/me/",
            {"timezone": "Asia/Kolkata"},
            format="json",
        )
        assert response.status_code == 401