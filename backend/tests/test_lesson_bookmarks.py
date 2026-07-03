import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from apps.content.models import Lesson
from apps.progress.models import LessonBookmark


@pytest.fixture
def lesson():
    return Lesson.objects.create(
        difficulty="beginner",
        title="What is Open Source",
        slug="what-is-open-source",
        summary="Intro to open source",
        content="Open source content",
        estimated_minutes=10,
        order=1,
    )


@pytest.fixture
def user():
    return User.objects.create_user(username="testuser", password="testpass123")


@pytest.fixture
def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_list_returns_only_caller_bookmarks(auth_client, user, lesson):
    other_user = User.objects.create_user(username="other", password="otherpass")
    LessonBookmark.objects.create(user=user, lesson=lesson)
    LessonBookmark.objects.create(user=other_user, lesson=lesson)
    response = auth_client.get("/api/progress/bookmarks/")
    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["lesson_slug"] == "what-is-open-source"


@pytest.mark.django_db
def test_post_creates_bookmark(auth_client, lesson):
    response = auth_client.post(f"/api/progress/bookmarks/{lesson.slug}/")
    assert response.status_code == 201
    assert LessonBookmark.objects.count() == 1


@pytest.mark.django_db
def test_post_is_idempotent(auth_client, user, lesson):
    LessonBookmark.objects.create(user=user, lesson=lesson)
    response = auth_client.post(f"/api/progress/bookmarks/{lesson.slug}/")
    assert response.status_code == 200
    assert LessonBookmark.objects.count() == 1


@pytest.mark.django_db
def test_delete_removes_bookmark(auth_client, user, lesson):
    LessonBookmark.objects.create(user=user, lesson=lesson)
    response = auth_client.delete(f"/api/progress/bookmarks/{lesson.slug}/")
    assert response.status_code == 204
    assert LessonBookmark.objects.count() == 0


@pytest.mark.django_db
def test_delete_is_idempotent(auth_client, lesson):
    response = auth_client.delete(f"/api/progress/bookmarks/{lesson.slug}/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_unauthenticated_request_rejected(lesson):
    client = APIClient()
    response = client.get("/api/progress/bookmarks/")
    assert response.status_code == 401