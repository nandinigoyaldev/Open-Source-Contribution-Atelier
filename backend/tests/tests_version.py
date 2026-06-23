from unittest.mock import patch

import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestVersionEndpoint:
    def test_returns_200(self, api_client):
        response = api_client.get("/api/version/")
        assert response.status_code == 200

    def test_returns_version_key(self, api_client):
        response = api_client.get("/api/version/")
        assert "version" in response.json()

    def test_uses_app_version_env_var_when_set(self, api_client, monkeypatch):
        monkeypatch.setenv("APP_VERSION", "v1.2.3")
        response = api_client.get("/api/version/")
        assert response.json()["version"] == "v1.2.3"

    def test_falls_back_to_git_commit_hash(self, api_client, monkeypatch):
        monkeypatch.delenv("APP_VERSION", raising=False)
        with patch("config.version_view._get_git_commit_hash", return_value="abc1234"):
            response = api_client.get("/api/version/")
        assert response.json()["version"] == "abc1234"

    def test_falls_back_to_unknown_when_no_git_available(self, api_client, monkeypatch):
        monkeypatch.delenv("APP_VERSION", raising=False)
        with patch("config.version_view._get_git_commit_hash", return_value=None):
            response = api_client.get("/api/version/")
        assert response.json()["version"] == "unknown"

    def test_no_authentication_required(self, api_client):
        # Explicitly unauthenticated client should still succeed
        response = api_client.get("/api/version/")
        assert response.status_code == 200
