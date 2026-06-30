from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from apps.content.models import Lesson
from apps.dashboard.models import Issue
from apps.progress.models import LessonProgress, XPMultiplierEvent


@pytest.fixture
def user():
    return User.objects.create_user(username="testuser", password="testpassword")


@pytest.fixture
def lesson():
    return Lesson.objects.create(slug="test-lesson", title="Test Lesson")


@pytest.fixture
def issue(user):
    return Issue.objects.create(title="Test Issue", assigned_to=user, points=50)


@pytest.mark.django_db
class TestXPMultiplier:

    def test_no_active_event(self, settings, user, lesson, issue):
        settings.CELERY_TASK_ALWAYS_EAGER = True
        client = APIClient()
        # 1. Lesson Progress creation without active event
        client.force_authenticate(user=user)
        response = client.post(
            "/api/progress/me/",
            {"lesson_slug": lesson.slug, "score": 100, "completed": True},
            format="json",
        )
        assert response.status_code == 201
        prog = LessonProgress.objects.get(user=user, lesson=lesson)
        assert prog.base_score == 100
        assert prog.score == 100
        assert prog.multiplier_applied == 1.0

        # 2. Issue solved without active event
        issue.status = Issue.Status.SOLVED
        issue.save()
        issue.refresh_from_db()
        assert issue.bonus_points == 0

    def test_active_event_multiplier(self, settings, user, lesson, issue):
        settings.CELERY_TASK_ALWAYS_EAGER = True
        client = APIClient()
        now = timezone.now()
        XPMultiplierEvent.objects.create(
            name="Weekend Bonus",
            multiplier=2.0,
            start_time=now - timedelta(days=1),
            end_time=now + timedelta(days=1),
            is_active=True,
        )

        # 1. Lesson Progress creation with active 2x event
        client.force_authenticate(user=user)
        response = client.post(
            "/api/progress/me/",
            {"lesson_slug": lesson.slug, "score": 100, "completed": True},
            format="json",
        )
        assert response.status_code == 201
        prog = LessonProgress.objects.get(user=user, lesson=lesson)
        assert prog.base_score == 100
        assert prog.score == 200
        assert prog.multiplier_applied == 2.0

        # 2. Issue solved with active 2x event
        issue.status = Issue.Status.SOLVED
        issue.save()
        issue.refresh_from_db()
        assert issue.points == 50
        assert issue.bonus_points == 50

    def test_inactive_or_expired_event(self, client, user, lesson, issue):
        now = timezone.now()
        # Expired event
        XPMultiplierEvent.objects.create(
            name="Old Event",
            multiplier=2.0,
            start_time=now - timedelta(days=10),
            end_time=now - timedelta(days=5),
            is_active=True,
        )
        # Inactive event
        XPMultiplierEvent.objects.create(
            name="Disabled Event",
            multiplier=1.5,
            start_time=now - timedelta(days=1),
            end_time=now + timedelta(days=1),
            is_active=False,
        )

        assert XPMultiplierEvent.get_active_multiplier() == 1.0

    def test_issue_status_reversion(self, user, issue):
        now = timezone.now()
        XPMultiplierEvent.objects.create(
            name="Weekend Bonus",
            multiplier=1.5,
            start_time=now - timedelta(days=1),
            end_time=now + timedelta(days=1),
            is_active=True,
        )

        issue.status = Issue.Status.SOLVED
        issue.save()
        issue.refresh_from_db()
        assert issue.bonus_points == 25  # 1.5x of 50

        # Change status back to open
        issue.status = Issue.Status.OPEN
        issue.save()
        issue.refresh_from_db()
        assert issue.bonus_points == 0
