import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.content.models import Lesson
from apps.progress.models import LessonProgress


@pytest.mark.django_db
def test_bulk_sync_creates_multiple_progress_records():
    user = User.objects.create_user(username="testuser", password="strongpass123")

    Lesson.objects.create(
        slug="git-basics",
        title="Git Basics",
        summary="summary",
        content="content",
        order=1,
    )

    Lesson.objects.create(
        slug="branches",
        title="Branches",
        summary="summary",
        content="content",
        order=2,
    )

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        "/api/progress/bulk-sync/",
        {
            "lessons": [
                {
                    "lesson_slug": "git-basics",
                    "score": 100,
                    "completed": True,
                },
                {
                    "lesson_slug": "branches",
                    "score": 90,
                    "completed": True,
                },
            ]
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.data["synced_count"] == 2
    assert LessonProgress.objects.filter(user=user).count() == 2
