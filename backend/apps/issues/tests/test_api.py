import pytest
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.issues.models import IssueReport
from django.core.files.uploadedfile import SimpleUploadedFile

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def regular_user(db):
    return User.objects.create_user(
        username="testuser", email="test@example.com", password="password123"
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        username="admin", email="admin@example.com", password="password123"
    )


@pytest.mark.django_db
class TestIssueReportAPI:
    def test_submit_issue_anonymous_success(self, api_client):
        response = api_client.post(
            "/api/issues/",
            {
                "title": "Broken link in lesson 1",
                "description": "Clicking the link gives 404.",
                "issue_type": "Bug",
                "url_path": "/lessons/1",
            },
        )
        assert response.status_code == 201
        assert IssueReport.objects.count() == 1
        issue = IssueReport.objects.first()
        assert issue.title == "Broken link in lesson 1"
        assert issue.user is None

    def test_submit_issue_authenticated_success(self, api_client, regular_user):
        api_client.force_authenticate(user=regular_user)
        response = api_client.post(
            "/api/issues/",
            {
                "title": "Typo in python tutorial",
                "description": "Spelled 'function' as 'functon'",
                "issue_type": "Content",
            },
        )
        assert response.status_code == 201
        assert IssueReport.objects.count() == 1
        issue = IssueReport.objects.first()
        assert issue.user == regular_user

    def test_submit_issue_missing_required_fields(self, api_client):
        response = api_client.post("/api/issues/", {"title": "", "description": ""})
        assert response.status_code == 400
        errors = response.data.get("errors", response.data)
        assert "title" in errors
        assert "description" in errors

    def test_submit_issue_with_image(self, api_client):
        valid_image_bytes = b"GIF89a\x01\x00\x01\x00\x00\xff\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        image = SimpleUploadedFile(
            "test_image.gif", valid_image_bytes, content_type="image/gif"
        )
        response = api_client.post(
            "/api/issues/",
            {
                "title": "UI overlap",
                "description": "Buttons overlap on mobile",
                "issue_type": "UI",
                "image": image,
            },
            format="multipart",
        )
        assert response.status_code == 201, response.data
        issue = IssueReport.objects.first()
        assert issue.image.name.startswith("issue_reports/test_image")

    def test_list_issues_unauthorized(self, api_client, regular_user):
        # Anonymous
        response = api_client.get("/api/issues/")
        assert response.status_code in [401, 403]

        # Regular user
        api_client.force_authenticate(user=regular_user)
        response = api_client.get("/api/issues/")
        assert response.status_code == 403

    def test_list_issues_admin(self, api_client, admin_user):
        IssueReport.objects.create(title="Test", description="Test desc")
        api_client.force_authenticate(user=admin_user)
        response = api_client.get("/api/issues/")
        assert response.status_code == 200
        assert len(response.data) == 1

    def test_patch_issue_status_admin(self, api_client, admin_user):
        issue = IssueReport.objects.create(title="Test", description="Test desc")
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            f"/api/issues/{issue.id}/", {"status": "In Progress"}
        )
        assert response.status_code == 200
        issue.refresh_from_db()
        assert issue.status == "In Progress"
