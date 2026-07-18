import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.notifications.models import NotificationPreference

User = get_user_model()


@pytest.fixture
def auth_client(db):
    user = User.objects.create_user(
        username="prefs_user", email="prefs@example.com", password="testpass123"
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


@pytest.mark.django_db
def test_notification_prefs_requires_auth():
    client = APIClient()
    response = client.get("/api/notifications/prefs/")
    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_notification_prefs_get_creates_defaults(auth_client):
    client, user = auth_client
    assert NotificationPreference.objects.filter(user=user).count() == 0

    response = client.get("/api/notifications/prefs/")
    assert response.status_code == 200
    assert response.data == {"email": True, "in_app": True, "websocket": True}
    assert NotificationPreference.objects.filter(user=user).count() == 1


@pytest.mark.django_db
def test_notification_prefs_put_updates(auth_client):
    client, user = auth_client

    response = client.put(
        "/api/notifications/prefs/",
        {"email": False, "in_app": True, "websocket": False},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["email"] is False
    assert response.data["in_app"] is True
    assert response.data["websocket"] is False

    prefs = NotificationPreference.objects.get(user=user)
    assert prefs.email_enabled is False
    assert prefs.in_app_enabled is True
    assert prefs.websocket_enabled is False


@pytest.mark.django_db
def test_notification_prefs_patch_partial(auth_client):
    client, user = auth_client
    NotificationPreference.objects.create(
        user=user, email_enabled=True, in_app_enabled=True, websocket_enabled=True
    )

    response = client.patch(
        "/api/notifications/prefs/",
        {"email": False},
        format="json",
    )
    assert response.status_code == 200
    prefs = NotificationPreference.objects.get(user=user)
    assert prefs.email_enabled is False
    assert prefs.in_app_enabled is True
    assert prefs.websocket_enabled is True
