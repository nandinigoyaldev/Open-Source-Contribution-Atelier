import pytest
from unittest.mock import patch
from django.contrib.auth.models import User
from apps.progress.models import (
    ExerciseAttempt,
    Achievement,
    UserAchievement,
    LessonProgress,
)
from apps.content.models import Exercise, Lesson
from apps.progress.tasks import evaluate_achievements_task
from apps.notifications.models import Notification


@pytest.fixture
def test_user(db):
    return User.objects.create_user(
        username="achiever", email="test@example.com", password="password"
    )


@pytest.fixture
def custom_lesson(db):
    return Lesson.objects.create(slug="test-lesson", title="Test", category="general")


@pytest.fixture
def custom_exercises(db, custom_lesson):
    exercises = []
    for i in range(10):
        exercises.append(
            Exercise.objects.create(
                lesson=custom_lesson, title=f"Ex {i}", prompt="Do it"
            )
        )
    return exercises


@pytest.fixture
def mock_channel_layer():
    with patch("channels.layers.get_channel_layer") as mock_layer:
        with patch("apps.notifications.signals.send_web_push_notification.delay"):
            with patch(
                "apps.notifications.signals.channel_layer", mock_layer, create=True
            ):
                yield mock_layer


@pytest.mark.django_db
def test_achievement_milestones(
    test_user, custom_exercises, custom_lesson, mock_channel_layer
):
    # Complete 1 challenge
    ExerciseAttempt.objects.create(
        user=test_user, exercise=custom_exercises[0], is_correct=True
    )
    # The signal should have triggered the task, but we can call it manually to be sure in tests if Celery isn't running inline
    evaluate_achievements_task(test_user.id)

    assert UserAchievement.objects.filter(
        user=test_user, achievement__slug="first-challenge"
    ).exists()
    assert (
        Notification.objects.filter(
            recipient=test_user, notif_type="achievement"
        ).count()
        == 1
    )

    # Complete 4 more challenges
    for i in range(1, 5):
        ExerciseAttempt.objects.create(
            user=test_user, exercise=custom_exercises[i], is_correct=True
        )

    evaluate_achievements_task(test_user.id)

    assert UserAchievement.objects.filter(
        user=test_user, achievement__slug="five-challenges"
    ).exists()
    # Notification count should now be 2
    assert (
        Notification.objects.filter(
            recipient=test_user, notif_type="achievement"
        ).count()
        == 2
    )

    # Complete a lesson
    LessonProgress.objects.create(
        user=test_user, lesson=custom_lesson, completed=True, score=100
    )
    evaluate_achievements_task(test_user.id)
    assert UserAchievement.objects.filter(
        user=test_user, achievement__slug="first-lesson"
    ).exists()
    assert (
        Notification.objects.filter(
            recipient=test_user, notif_type="achievement"
        ).count()
        == 3
    )
