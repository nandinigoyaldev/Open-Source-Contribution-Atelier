import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from .models import CodeSnapshot


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user():
    return User.objects.create_user(username="testuser", password="password")


@pytest.fixture
def user2():
    return User.objects.create_user(username="testuser2", password="password")


@pytest.mark.django_db
class TestCodeSnapshotViewSet:
    def test_create_snapshot_unauthenticated(self, api_client):
        response = api_client.post(
            "/api/sandbox/snapshots/", {"code": "print('hello')"}
        )
        assert response.status_code == 401

    def test_create_snapshot_authenticated(self, api_client, user):
        api_client.force_authenticate(user=user)
        response = api_client.post(
            "/api/sandbox/snapshots/",
            {"code": "print('hello')", "label": "test label", "is_auto": False},
        )
        assert response.status_code == 201
        assert CodeSnapshot.objects.count() == 1
        snapshot = CodeSnapshot.objects.first()
        assert snapshot.user == user
        assert snapshot.code == "print('hello')"
        assert snapshot.label == "test label"
        assert snapshot.is_auto is False

    def test_create_snapshot_default_auto(self, api_client, user):
        api_client.force_authenticate(user=user)
        response = api_client.post(
            "/api/sandbox/snapshots/", {"code": "print('hello2')"}
        )
        assert response.status_code == 201
        snapshot = CodeSnapshot.objects.first()
        assert snapshot.is_auto is True
        assert snapshot.label == ""

    def test_list_snapshots_returns_only_user_snapshots(self, api_client, user, user2):
        CodeSnapshot.objects.create(user=user, code="user1 code")
        CodeSnapshot.objects.create(user=user2, code="user2 code")

        api_client.force_authenticate(user=user)
        response = api_client.get("/api/sandbox/snapshots/")

        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["code"] == "user1 code"

    def test_list_snapshots_ordering(self, api_client, user):
        api_client.force_authenticate(user=user)
        CodeSnapshot.objects.create(user=user, code="older")
        CodeSnapshot.objects.create(user=user, code="newer")

        response = api_client.get("/api/sandbox/snapshots/")
        assert response.status_code == 200
        assert len(response.data) == 2
        # ordered by -timestamp, so newer first
        assert response.data[0]["code"] == "newer"
        assert response.data[1]["code"] == "older"
