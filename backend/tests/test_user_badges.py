import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.content.models import Lesson
from apps.progress.models import Badge, LessonProgress, UserBadge
from apps.progress.tasks import evaluate_achievements_task


def create_lesson(slug="intro"):
    return Lesson.objects.create(
        difficulty="beginner",
        title="Intro",
        slug=slug,
        summary="Learn the basics.",
        content="Lesson content",
    )


@pytest.mark.django_db
def test_authenticated_user_can_retrieve_badges_and_progress_points():
    user = User.objects.create_user(username="learner", password="strongpass123")
    badge = Badge.objects.create(
        name="First Steps",
        slug="first-lesson",
        description="Completed your first lesson.",
    )
    UserBadge.objects.create(user=user, badge=badge)
    LessonProgress.objects.create(
        user=user, lesson=create_lesson(), completed=True, score=75
    )
    LessonProgress.objects.create(
        user=user, lesson=create_lesson("branching"), completed=True, score=25
    )
    evaluate_achievements_task(user.id)

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get("/api/users/me/badges/")

    assert response.status_code == 200
    assert response.data["progress_points"] == 100
    # The signal (dashboard/signals) from LessonProgress creation awards "first-lesson" badge
    slugs = [b["slug"] for b in response.data["badges"]]
    assert "first-lesson" in slugs
    assert len(slugs) == 1
    assert response.data["badges"][0]["earned_at"]


@pytest.mark.django_db
def test_badges_endpoint_requires_authentication():
    client = APIClient()

    response = client.get("/api/users/me/badges/")

    assert response.status_code == 401


@pytest.mark.django_db
def test_badges_endpoint_returns_only_authenticated_users_stats():
    user = User.objects.create_user(username="learner", password="strongpass123")
    other_user = User.objects.create_user(username="other", password="strongpass123")
    own_badge = Badge.objects.create(
        name="Own Badge",
        slug="own-badge",
        description="Belongs to the authenticated user.",
    )
    other_badge = Badge.objects.create(
        name="Other Badge",
        slug="other-badge",
        description="Belongs to someone else.",
    )
    UserBadge.objects.create(user=user, badge=own_badge)
    UserBadge.objects.create(user=other_user, badge=other_badge)
    LessonProgress.objects.create(
        user=user, lesson=create_lesson(), completed=True, score=40
    )
    LessonProgress.objects.create(
        user=other_user, lesson=create_lesson("other"), completed=True, score=90
    )
    evaluate_achievements_task(user.id)
    evaluate_achievements_task(other_user.id)

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get("/api/users/me/badges/")

    assert response.status_code == 200
    assert response.data["progress_points"] == 40
    # The signal (dashboard/signals) from creating LessonProgress awards the "first-lesson" badge
    badge_slugs = [badge["slug"] for badge in response.data["badges"]]
    assert "own-badge" in badge_slugs
    assert "first-lesson" in badge_slugs
    assert "other-badge" not in badge_slugs


@pytest.mark.django_db
def test_lesson_completion_automatically_awards_badges_and_notifies():
    from apps.notifications.models import Notification

    user = User.objects.create_user(username="newbie", password="strongpass123")
    create_lesson("intro")
    create_lesson("first-contribution-walkthrough")
    client = APIClient()
    client.force_authenticate(user=user)

    # 1. Complete a lesson that should unlock the "First Steps" badge (min_lessons=1)
    response = client.post(
        "/api/progress/me/",
        {
            "lesson_slug": "intro",
            "score": 100,
            "completed": True,
        },
        format="json",
    )
    assert response.status_code == 201

    evaluate_achievements_task(user.id)

    # Check if the "first-lesson" badge was automatically created and awarded
    assert UserBadge.objects.filter(user=user, badge__slug="first-lesson").exists()

    # 2. Check if a notification was generated for the badge award
    assert Notification.objects.filter(
        recipient=user, notif_type="badge", meta__badge_slug="first-lesson"
    ).exists()
