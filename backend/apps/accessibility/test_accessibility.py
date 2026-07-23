import pytest
from rest_framework.test import APIClient
from apps.accessibility.models import A11yIssue


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
def test_a11y_issue_creation():
    issue = A11yIssue.objects.create(
        route="/dashboard",
        selector=".btn-primary",
        violation_type="color-contrast",
        severity="moderate",
    )
    assert issue.pk is not None
    assert str(issue) == "color-contrast on /dashboard"


@pytest.mark.django_db
def test_a11y_issue_api(api_client):
    response = api_client.get("/api/accessibility/issues/")
    # Requires admin permissions, so anonymous user should get 401 or 403
    assert response.status_code in [401, 403]
