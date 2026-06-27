from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestLeaderboardCaching:
    def test_returns_200(self, api_client):
        response = api_client.get("/api/leaderboard/")
        assert response.status_code == 200

    def test_caches_response_on_first_call(self, api_client):
        api_client.get("/api/leaderboard/")
        assert cache.get("leaderboard_page_1") is not None

    def test_second_call_uses_cache_not_db(self, api_client):
        api_client.get("/api/leaderboard/")

        with patch(
            "apps.dashboard.views.LeaderboardView.get_queryset"
        ) as mock_get_queryset:
            response = api_client.get("/api/leaderboard/")
            mock_get_queryset.assert_not_called()
        assert response.status_code == 200

    def test_different_pages_cached_separately(self, api_client):
        for i in range(25):
            User.objects.create_user(username=f"user{i}", password="pw12345!")

        api_client.get("/api/leaderboard/?page=1")
        api_client.get("/api/leaderboard/?page=2")

        assert cache.get("leaderboard_page_1") is not None
        assert cache.get("leaderboard_page_2") is not None
        assert cache.get("leaderboard_page_1") != cache.get("leaderboard_page_2")

    def test_cache_expires_after_ttl(self, api_client):
        with patch("apps.dashboard.views.cache.set") as mock_set:
            api_client.get("/api/leaderboard/")
            mock_set.assert_called_once()
            _, _, ttl = mock_set.call_args[0]
            assert ttl == 300
