import pytest
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


def test_health_live_view(api_client):
    response = api_client.get("/health/live/")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_health_ready_view(api_client, mocker):
    mocker.patch(
        "apps.health.views.HealthChecker.run_checks", return_value={"status": "healthy"}
    )
    response = api_client.get("/health/ready/")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_health_view_success(api_client, mocker):
    mocker.patch(
        "apps.health.views.HealthChecker.run_checks", return_value={"status": "healthy"}
    )
    response = api_client.get("/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
