import datetime
import pytest
from django.urls import reverse
from rest_framework import status
from django.contrib.auth.models import User

from apps.content.models import Lesson, Exercise
from apps.progress.models import StreakProfile, StreakRecoveryPlan, QuizAttempt, ExerciseAttempt
from apps.progress.services.streak_recovery_service import StreakRecoveryService


@pytest.fixture
def setup_data(db):
    user = User.objects.create_user(username="testuser", password="password")
    
    # Create StreakProfile
    profile = StreakProfile.objects.create(
        user=user,
        current_streak=5,
        longest_streak=5,
        last_activity_date=datetime.date.today() - datetime.timedelta(days=2) # missed yesterday
    )
    
    lesson = Lesson.objects.create(
        difficulty="easy",
        title="Test Lesson",
        slug="test-lesson",
        summary="summary",
        content="content"
    )
    
    exercise = Exercise.objects.create(
        lesson=lesson,
        title="Test Exercise",
        prompt="prompt",
        expected_command="git status"
    )
    
    return user, profile, lesson, exercise


@pytest.mark.django_db
class TestStreakRecovery:
    def test_streak_status_endpoint(self, api_client, setup_data):
        user, profile, _, _ = setup_data
        api_client.force_authenticate(user=user)

        response = api_client.get(reverse("streak-status"))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["current_streak"] == 5
        assert response.data["highest_streak"] == 5
        assert response.data["multiplier"] == 1.1

    def test_get_or_create_recovery_plan_eligible(self, setup_data):
        user, _, _, _ = setup_data
        plan = StreakRecoveryService.get_or_create_recovery_plan(user)
        
        assert plan is not None
        assert plan.previous_streak == 5
        assert plan.quiz_target == 1
        assert plan.reading_target == 15
        assert plan.code_target == 1
        assert plan.is_completed is False

    def test_get_or_create_recovery_plan_not_eligible(self, setup_data):
        user, profile, _, _ = setup_data
        # Update last_activity_date to today (not missed)
        profile.last_activity_date = datetime.date.today()
        profile.save()

        plan = StreakRecoveryService.get_or_create_recovery_plan(user)
        assert plan is None

    def test_sync_and_update_progress(self, setup_data):
        user, _, lesson, exercise = setup_data
        
        # Generates plan
        plan = StreakRecoveryService.get_or_create_recovery_plan(user)
        assert plan is not None

        # 1. Complete quiz
        QuizAttempt.objects.create(
            user=user,
            question_id="q1",
            is_correct=True
        )

        # 2. Complete code submission
        ExerciseAttempt.objects.create(
            user=user,
            exercise=exercise,
            is_correct=True
        )

        # Sync progress
        plan = StreakRecoveryService.sync_and_update_progress(plan)
        assert plan.quiz_progress == 1
        assert plan.code_progress == 1
        assert plan.is_completed is False # reading still not completed

        # 3. Simulate reading time (reading progress to 15)
        plan.reading_progress = 15
        plan.save()

        # Sync progress again
        plan = StreakRecoveryService.sync_and_update_progress(plan)
        assert plan.is_completed is True

        # Check that StreakProfile is recovered
        profile = StreakProfile.objects.get(user=user)
        assert profile.current_streak == 6 # recovered! previous_streak 5 + 1
        assert profile.last_activity_date == datetime.date.today()

    def test_reading_progress_endpoint_increments_minutes(self, api_client, setup_data):
        user, _, lesson, _ = setup_data
        api_client.force_authenticate(user=user)

        # Initial check
        plan = StreakRecoveryService.get_or_create_recovery_plan(user)
        assert plan is not None
        assert plan.reading_progress == 0

        # Post reading progress
        response = api_client.post(
            reverse("reading-position"),
            {"lesson": lesson.slug, "progress": 50},
            format="json"
        )
        assert response.status_code == status.HTTP_200_OK

        # Assert reading_progress incremented
        plan.refresh_from_db()
        assert plan.reading_progress == 1
