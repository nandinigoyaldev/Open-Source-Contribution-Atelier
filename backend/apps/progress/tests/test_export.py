from io import BytesIO
from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from django.contrib.auth import get_user_model
from apps.progress.models import StreakProfile

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user():
    user = User.objects.create_user(
        username="testuser", password="password", email="test@example.com"
    )
    StreakProfile.objects.create(user=user, current_streak=5, longest_streak=10)
    return user


@pytest.mark.django_db
class TestUserProgressPDFExport:
    def test_unauthenticated_access(self, api_client):
        url = reverse("export-pdf")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_authenticated_pdf_export(self, api_client, user):
        api_client.force_authenticate(user=user)
        url = reverse("export-pdf")

        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "application/pdf"
        assert (
            response["Content-Disposition"]
            == 'attachment; filename="progress_report.pdf"'
        )

        assert len(response.content) > 0
        assert response.content.startswith(b"%PDF-")

    def test_edge_case_empty_user(self, api_client):
        # User with NO streak, NO progress, NO badges
        empty_user = User.objects.create_user(
            username="empty_user", password="password", email="empty@example.com"
        )
        api_client.force_authenticate(user=empty_user)

        url = reverse("export-pdf")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.content.startswith(b"%PDF-")

    def test_edge_case_long_strings(self, api_client):
        from apps.progress.models import LessonProgress
        from apps.content.models import Lesson

        # User with extremely long strings to test table truncation
        long_user = User.objects.create_user(username="long_user", password="password")
        StreakProfile.objects.create(user=long_user, current_streak=1, longest_streak=1)

        very_long_title = "A" * 150
        lesson = Lesson.objects.create(
            slug="long-lesson",
            title=very_long_title,
            summary="test",
            content="test",
            difficulty="beginner",
        )
        LessonProgress.objects.create(
            user=long_user, lesson=lesson, completed=True, score=100
        )

        api_client.force_authenticate(user=long_user)
        url = reverse("export-pdf")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.content.startswith(b"%PDF-")
