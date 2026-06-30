import pytest
from apps.content.models import Exercise, Lesson
from apps.progress.models import LessonProgress
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def clear_cache_before_tests():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db(transaction=True)
def test_roadmap_endpoint_for_anonymous_user():
    lesson = Lesson.objects.create(
        difficulty="beginner",
        title="Intro",
        slug="intro-roadmap",
        summary="Intro summary",
        content="Intro content",
        estimated_minutes=10,
        order=1,
    )
    Exercise.objects.create(
        lesson=lesson,
        title="Exercise 1",
        prompt="Run git status",
        expected_command="git status",
        explanation="Status command",
        points=10,
    )

    client = APIClient()
    response = client.get("/api/content/roadmap/")

    assert response.status_code == 200
    assert response.data["stats"]["total_lessons"] == 1
    assert response.data["track"][0]["slug"] == "intro-roadmap"
    assert response.data["track"][0]["exercise_count"] == 1
    assert response.data["track"][0]["completed"] is False
    assert response.data["track"][0]["score"] == 0


@pytest.mark.django_db(transaction=True)
def test_roadmap_endpoint_includes_user_progress():
    lesson = Lesson.objects.create(
        difficulty="beginner",
        title="Branching",
        slug="branching-roadmap",
        summary="Branching summary",
        content="Branching content",
        estimated_minutes=12,
        order=2,
    )

    user = User.objects.create_user(username="roadmap_user", password="strongpass123")
    LessonProgress.objects.create(user=user, lesson=lesson, completed=True, score=95)

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get("/api/content/roadmap/")

    assert response.status_code == 200
    assert response.data["stats"]["total_lessons"] == 1
    assert response.data["stats"]["completed_lessons"] == 1
    assert response.data["track"][0]["slug"] == "branching-roadmap"
    assert response.data["track"][0]["completed"] is True
    assert response.data["track"][0]["score"] == 95


@pytest.mark.django_db
def test_estimated_minutes_below_range_raises_validation_error():
    lesson = Lesson(
        difficulty="beginner",
        title="Invalid Low",
        slug="invalid-low",
        summary="summary",
        content="content",
        estimated_minutes=0,
        order=1,
    )

    with pytest.raises(ValidationError):
        lesson.full_clean()


@pytest.mark.django_db
def test_estimated_minutes_above_range_raises_validation_error():
    lesson = Lesson(
        difficulty="beginner",
        title="Invalid High",
        slug="invalid-high",
        summary="summary",
        content="content",
        estimated_minutes=121,
        order=1,
    )

    with pytest.raises(ValidationError):
        lesson.full_clean()
