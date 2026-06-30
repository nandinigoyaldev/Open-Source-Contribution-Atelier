import pytest
from django.urls import reverse
from rest_framework import status
from django.contrib.auth.models import User
from apps.progress.models import LessonProgress, ExerciseAttempt
from apps.content.models import Lesson, Exercise
from apps.dashboard.models import Issue, StreakFreeze
from datetime import timedelta
from django.utils import timezone


@pytest.fixture
def test_users(db):
    user1 = User.objects.create_user(
        username="testuser1", email="test1@example.com", password="password"
    )
    user2 = User.objects.create_user(
        username="testuser2", email="test2@example.com", password="password"
    )
    admin = User.objects.create_superuser(
        username="admin", email="admin@example.com", password="password"
    )
    return user1, user2, admin


from django.test import override_settings


@pytest.fixture
@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
def custom_data(db, test_users):
    user1, user2, admin = test_users

    lesson1 = Lesson.objects.create(
        slug="lesson-1", title="Lesson 1", category="general"
    )
    lesson2 = Lesson.objects.create(
        slug="lesson-2", title="Lesson 2", category="general"
    )

    # User 1 completes 1 lesson
    from unittest.mock import patch

    with patch("apps.progress.tasks.evaluate_user_badges_task.delay"), patch(
        "apps.notifications.signals.send_web_push_notification.delay"
    ), patch("celery.app.task.Task.delay"):
        LessonProgress.objects.create(
            user=user1, lesson=lesson1, completed=True, score=100
        )

        # User 1 solves 1 issue
        Issue.objects.create(
            title="Issue 1",
            assigned_to=user1,
            status=Issue.Status.SOLVED,
            points=50,
            bonus_points=10,
        )

    # User 1 uses a streak freeze
    StreakFreeze.objects.create(
        user=user1,
        used_on_date=timezone.localdate(timezone.now() - timedelta(days=1)),
        cost=100,
    )

    return user1, user2, admin


@pytest.mark.django_db
def test_csv_export_unauthorized(custom_data):
    from rest_framework.test import APIClient

    client = APIClient()
    url = reverse("export-progress-csv")
    response = client.get(url)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    user1, user2, admin = custom_data
    client.force_authenticate(user=user1)
    response = client.get(url)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_csv_export_authorized(custom_data):
    from rest_framework.test import APIClient

    client = APIClient()
    user1, user2, admin = custom_data
    client.force_authenticate(user=admin)

    url = reverse("export-progress-csv")
    response = client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert response["Content-Type"] == "text/csv"
    assert (
        'attachment; filename="user_progress_report.csv"'
        in response["Content-Disposition"]
    )

    # StreamingHttpResponse uses streaming_content
    content = b"".join(response.streaming_content).decode("utf-8")
    lines = content.strip().split("\r\n")

    assert len(lines) == 3  # Header + 2 non-staff users
    assert (
        lines[0]
        == "Username,Email,Completed Modules,Completed Challenges,XP Earned,Current Learning Streak,Highest Streak,Completion Percentage,Last Active Date,Account Creation Date"
    )

    # Check user1 data
    user1_line = [line for line in lines if line.startswith("testuser1")][0]
    cols = user1_line.split(",")
    assert cols[0] == "testuser1"
    assert cols[1] == "test1@example.com"
    assert cols[2] == "1"  # 1 module
    assert cols[3] == "0"  # 0 challenges
    assert cols[4] == "160"  # 100 + 50 + 10 XP

    # Check user2 data
    user2_line = [line for line in lines if line.startswith("testuser2")][0]
    cols2 = user2_line.split(",")
    assert cols2[0] == "testuser2"
    assert cols2[4] == "0"  # 0 XP
