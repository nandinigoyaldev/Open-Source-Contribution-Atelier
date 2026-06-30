import io
import json
import zipfile
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.chat.models import Message
from apps.content.models import Comment, Exercise, Lesson
from apps.dashboard.models import Issue, StreakFreeze
from apps.progress.models import (
    CodeSubmission,
    ExerciseAttempt,
    LessonProgress,
    PeerReview,
    UserBadge,
)

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user():
    return User.objects.create_user(
        username="testuser", email="test@example.com", password="password"
    )


@pytest.fixture
def other_user():
    return User.objects.create_user(
        username="otheruser", email="other@example.com", password="password"
    )


@pytest.fixture
def setup_user_data(user, other_user):
    # Setup Lesson, Exercise, etc.
    lesson = Lesson.objects.create(
        title="Test Lesson", slug="test-lesson", summary="summary", content="content"
    )
    exercise = Exercise.objects.create(
        lesson=lesson, title="Test Ex", prompt="Prompt", expected_command="echo"
    )

    # Create user data
    LessonProgress.objects.create(user=user, lesson=lesson, completed=True)
    ExerciseAttempt.objects.create(
        user=user, exercise=exercise, submitted_command="echo", is_correct=True
    )
    submission = CodeSubmission.objects.create(
        user=user, title="My PR", code_snippet="print(1)"
    )
    PeerReview.objects.create(submission=submission, reviewer=user, feedback="Good job")
    StreakFreeze.objects.create(user=user)
    Issue.objects.create(title="My Issue", assigned_to=user)
    Comment.objects.create(user=user, lesson=lesson, content="Great lesson")
    Message.objects.create(user=user, room_id="room1", content="Hello world")

    # Create other user data to test isolation
    LessonProgress.objects.create(user=other_user, lesson=lesson, completed=True)
    Comment.objects.create(user=other_user, lesson=lesson, content="Other comment")


@pytest.mark.django_db
class TestDataExport:
    def test_unauthenticated_access_denied(self, api_client):
        response = api_client.get("/api/auth/me/export/?export_format=json")
        assert response.status_code == 401

    def test_json_export(self, api_client, user, setup_user_data):
        api_client.force_authenticate(user=user)
        response = api_client.get("/api/auth/me/export/?export_format=json")
        assert response.status_code == 200
        assert response["Content-Type"] == "application/json"

        data = response.json()
        assert "user_profile" in data
        assert "lesson_progress" in data
        assert "exercise_attempts" in data
        assert "code_submissions" in data
        assert "peer_reviews" in data
        assert "streak_freezes" in data
        assert "assigned_issues" in data
        assert "comments" in data
        assert "messages" in data

        # Check aggregation
        assert len(data["lesson_progress"]) == 1
        assert len(data["comments"]) == 1
        assert data["comments"][0]["content"] == "Great lesson"
        assert len(data["messages"]) == 1
        assert data["messages"][0]["content"] == "Hello world"

    def test_csv_zip_export(self, api_client, user, setup_user_data):
        api_client.force_authenticate(user=user)
        response = api_client.get("/api/auth/me/export/?export_format=csv")
        assert response.status_code == 200
        assert response["Content-Type"] == "application/zip"

        # Verify ZIP archive
        zip_buffer = io.BytesIO(response.content)
        with zipfile.ZipFile(zip_buffer, "r") as zf:
            files = zf.namelist()
            assert "user_profile.csv" in files
            assert "lesson_progress.csv" in files
            assert "comments.csv" in files

            # Read a specific file from the archive
            with zf.open("comments.csv") as f:
                content = f.read().decode("utf-8")
                assert "Great lesson" in content
                assert "Other comment" not in content

    def test_data_isolation(self, api_client, other_user, setup_user_data):
        api_client.force_authenticate(user=other_user)
        response = api_client.get("/api/auth/me/export/?export_format=json")
        assert response.status_code == 200
        data = response.json()

        assert len(data["lesson_progress"]) == 1
        assert len(data["comments"]) == 1
        assert data["comments"][0]["content"] == "Other comment"

        # Other user has no messages or exercises
        assert len(data["messages"]) == 0
        assert len(data["exercise_attempts"]) == 0
