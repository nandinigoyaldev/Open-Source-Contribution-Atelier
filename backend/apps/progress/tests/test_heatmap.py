import json
from datetime import timedelta

from apps.content.models import Exercise, Lesson
from apps.progress.models import ExerciseAttempt, LessonProgress, QuizAttempt
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


class ActivityHeatmapTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="heatmapuser", password="password123", email="heatmap@example.com"
        )
        self.client.force_authenticate(user=self.user)
        self.url = reverse("activity-heatmap")

        self.lesson = Lesson.objects.create(
            title="Intro",
            slug="intro",
            difficulty="beginner",
            category="general",
            estimated_minutes=15,
            summary="A short summary",
            content="Lesson content",
        )
        self.exercise = Exercise.objects.create(
            lesson=self.lesson,
            title="Exercise 1",
            prompt="Do something",
            expected_command="git status",
        )

    def test_heatmap_aggregation(self):
        # Create activities across different dates
        today = timezone.now()
        yesterday = today - timedelta(days=1)
        two_days_ago = today - timedelta(days=2)

        # Lesson progress today
        progress = LessonProgress.objects.create(
            user=self.user, lesson=self.lesson, completed=True, score=100
        )
        # We need to manually set updated_at because auto_now overwrites it on save
        LessonProgress.objects.filter(id=progress.id).update(updated_at=today)

        # Exercise attempt yesterday
        ExerciseAttempt.objects.create(
            user=self.user,
            exercise=self.exercise,
            submitted_command="git init",
            is_correct=True,
        )
        ExerciseAttempt.objects.filter(user=self.user).update(created_at=yesterday)

        # Quiz attempt two days ago
        QuizAttempt.objects.create(
            user=self.user,
            question_id="q1",
            question_text="What?",
            selected_answer="A",
            correct_answer="A",
            is_correct=True,
        )
        QuizAttempt.objects.filter(user=self.user).update(created_at=two_days_ago)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()

        # We expect 3 distinct dates with activity
        active_dates = {item["date"]: item["count"] for item in data}

        today_str = today.date().strftime("%Y-%m-%d")
        yesterday_str = yesterday.date().strftime("%Y-%m-%d")
        two_days_str = two_days_ago.date().strftime("%Y-%m-%d")

        self.assertEqual(active_dates.get(today_str), 1)
        self.assertEqual(active_dates.get(yesterday_str), 1)
        self.assertEqual(active_dates.get(two_days_str), 1)
