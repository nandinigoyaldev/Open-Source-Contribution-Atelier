import csv
import datetime

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status

from apps.content.models import Exercise, Lesson
from apps.progress.models import (
    DailyActivity,
    ExerciseAttempt,
    LessonProgress,
    QuizAttempt,
)


@pytest.fixture
def test_setup(db):
    user = User.objects.create_user(username="testuser", password="password")
    lesson = Lesson.objects.create(
        difficulty="easy",
        title="Test Lesson",
        slug="test-lesson",
        summary="summary",
        content="content",
    )
    exercise = Exercise.objects.create(
        lesson=lesson,
        title="Test Exercise",
        prompt="prompt",
        expected_command="git status",
    )
    return user, lesson, exercise


@pytest.mark.django_db
class TestHeatmapViews:
    def test_heatmap_empty(self, api_client, test_setup):
        user, _, _ = test_setup
        api_client.force_authenticate(user=user)

        response = api_client.get(reverse("heatmap"))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 0

    def test_heatmap_with_activities(self, api_client, test_setup):
        user, lesson, exercise = test_setup
        api_client.force_authenticate(user=user)

        today = datetime.date.today()

        # 1. Lesson completion
        LessonProgress.objects.create(
            user=user, lesson=lesson, completed=True, score=100
        )

        # 2. Quiz Attempt
        QuizAttempt.objects.create(
            user=user,
            question_id="q1",
            question_text="Q1?",
            selected_answer="A",
            correct_answer="A",
            is_correct=True,
        )

        # 3. Exercise Attempt
        ExerciseAttempt.objects.create(
            user=user, exercise=exercise, submitted_command="git init", is_correct=True
        )

        response = api_client.get(reverse("heatmap"))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

        entry = response.data[0]
        assert entry["date"] == today.isoformat()
        assert entry["count"] == 3
        assert entry["breakdown"]["reading"] == 1
        assert entry["breakdown"]["quizzes"] == 1
        assert entry["breakdown"]["code_submissions"] == 1

    def test_heatmap_filters(self, api_client, test_setup):
        user, lesson, exercise = test_setup
        api_client.force_authenticate(user=user)

        today = datetime.date.today()

        QuizAttempt.objects.create(user=user, question_id="q1", is_correct=True)
        ExerciseAttempt.objects.create(user=user, exercise=exercise, is_correct=True)

        # Filter by quizzes
        response = api_client.get(reverse("heatmap"), {"activity_type": "quizzes"})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["count"] == 1
        assert response.data[0]["breakdown"]["quizzes"] == 1

        # Filter by reading (empty)
        response = api_client.get(reverse("heatmap"), {"activity_type": "reading"})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 0

    def test_heatmap_csv_export(self, api_client, test_setup):
        user, lesson, exercise = test_setup
        api_client.force_authenticate(user=user)

        today = datetime.date.today()

        QuizAttempt.objects.create(user=user, question_id="q1", is_correct=True)

        response = api_client.get(reverse("heatmap-export-csv"))
        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "text/csv"
        assert "attachment; filename=" in response["Content-Disposition"]

        content = response.content.decode("utf-8")
        reader = csv.reader(content.splitlines())
        rows = list(reader)

        assert rows[0] == [
            "Date",
            "Activity Type",
            "Reading Count",
            "Quizzes Count",
            "Code Submissions Count",
            "Total Count",
        ]
        assert len(rows) > 1
        assert rows[1][0] == today.isoformat()
        assert rows[1][1] == "All Activities"
        assert rows[1][3] == "1"
        assert rows[1][5] == "1"

    def test_heatmap_aggregation_performance(
        self, api_client, test_setup, django_assert_num_queries
    ):
        user, lesson, _ = test_setup
        api_client.force_authenticate(user=user)

        progresses = [
            LessonProgress(user=user, lesson=lesson, completed=True, score=100)
            for _ in range(1000)
        ]
        LessonProgress.objects.bulk_create(progresses)

        url = reverse("heatmap")

        # Test number of queries is low (1 for user, some for the 3 queries)
        with django_assert_num_queries(5):
            response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["breakdown"]["reading"] == 1000

    def test_heatmap_limit(self, api_client, test_setup):
        user, lesson, _ = test_setup
        api_client.force_authenticate(user=user)

        LessonProgress.objects.create(
            user=user, lesson=lesson, completed=True, score=100
        )
        url = reverse("heatmap")
        response = api_client.get(url, {"limit": "1"})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
