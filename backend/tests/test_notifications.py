import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from apps.notifications.models import Notification


@pytest.fixture
def user_a(db):
    return User.objects.create_user(username="user_a", password="pass")


@pytest.fixture
def user_b(db):
    return User.objects.create_user(username="user_b", password="pass")


@pytest.fixture
def notif_for_a(db, user_a):
    return Notification.objects.create(
        recipient=user_a,
        message="Hello user_a",
        is_read=False,
    )


@pytest.fixture
def notif_for_b(db, user_b):
    return Notification.objects.create(
        recipient=user_b,
        message="Hello user_b",
        is_read=False,
    )


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_list_shows_only_own_notifications(user_a, user_b, notif_for_a, notif_for_b):
    client = auth_client(user_a)
    response = client.get("/api/notifications/")
    assert response.status_code == 200
    ids = [n["id"] for n in response.data]
    assert notif_for_a.id in ids
    assert notif_for_b.id not in ids


def test_list_requires_auth(db):
    client = APIClient()
    response = client.get("/api/notifications/")
    assert response.status_code == 401


def test_mark_one_read(user_a, notif_for_a):
    client = auth_client(user_a)
    response = client.post(f"/api/notifications/{notif_for_a.id}/read/")
    assert response.status_code == 200
    notif_for_a.refresh_from_db()
    assert notif_for_a.is_read is True


def test_mark_one_read_cannot_touch_other_users_notif(user_a, notif_for_b):
    client = auth_client(user_a)
    response = client.post(f"/api/notifications/{notif_for_b.id}/read/")
    assert response.status_code == 404


def test_mark_all_read(user_a, notif_for_a):
    client = auth_client(user_a)
    response = client.post("/api/notifications/mark-all-read/")
    assert response.status_code == 200
    assert response.data["marked_read"] >= 1
    notif_for_a.refresh_from_db()
    assert notif_for_a.is_read is True
