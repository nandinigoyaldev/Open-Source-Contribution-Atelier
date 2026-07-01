from django.contrib.auth.models import User
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.content.models import Lesson

from .models import LessonProgress


class BulkProgressUpdateTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="password123"
        )
        self.url = reverse("bulk-update")
        self.lesson1 = Lesson.objects.create(
            slug="lesson-1", title="Lesson 1", difficulty="beginner"
        )
        self.lesson2 = Lesson.objects.create(
            slug="lesson-2", title="Lesson 2", difficulty="beginner"
        )
        self.lesson3 = Lesson.objects.create(
            slug="lesson-3", title="Lesson 3", difficulty="beginner"
        )

    def test_unauthenticated_returns_401(self):
        response = self.client.post(self.url, {"lessons": []})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_valid_bulk_update_creates_new_progress(self):
        self.client.force_authenticate(user=self.user)
        payload = {
            "lessons": [
                {"lesson_slug": "lesson-1", "score": 90, "completed": True},
                {"lesson_slug": "lesson-2", "score": 80, "completed": False},
            ]
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["transaction_outcome"], "committed")
        self.assertEqual(response.data["updated_count"], 2)

        # Verify in DB
        self.assertEqual(LessonProgress.objects.count(), 2)
        p1 = LessonProgress.objects.get(lesson=self.lesson1)
        self.assertEqual(p1.score, 90)
        self.assertTrue(p1.completed)

        p2 = LessonProgress.objects.get(lesson=self.lesson2)
        self.assertEqual(p2.score, 80)
        self.assertFalse(p2.completed)

    def test_valid_bulk_update_updates_existing_progress(self):
        self.client.force_authenticate(user=self.user)
        # Create existing progress
        LessonProgress.objects.create(
            user=self.user, lesson=self.lesson1, score=50, completed=False
        )

        payload = {
            "lessons": [
                {"lesson_slug": "lesson-1", "score": 95, "completed": True},
                {"lesson_slug": "lesson-2", "score": 100, "completed": True},
            ]
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["updated_count"], 2)

        # Verify in DB
        p1 = LessonProgress.objects.get(lesson=self.lesson1)
        self.assertEqual(p1.score, 95)
        self.assertTrue(p1.completed)

    def test_invalid_lesson_id_rolls_back_transaction(self):
        self.client.force_authenticate(user=self.user)
        payload = {
            "lessons": [
                {"lesson_slug": "lesson-1", "score": 95, "completed": True},
                {"lesson_slug": "invalid-lesson-slug", "score": 100, "completed": True},
            ]
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])
        self.assertEqual(response.data["transaction_outcome"], "rolled_back")
        self.assertIn("invalid_lessons", response.data["validation_failures"])

        # Verify nothing was created (transaction rolled back)
        self.assertEqual(LessonProgress.objects.count(), 0)

    def test_duplicate_entries_rejected(self):
        self.client.force_authenticate(user=self.user)
        payload = {
            "lessons": [
                {"lesson_slug": "lesson-1", "score": 90, "completed": True},
                {"lesson_slug": "lesson-1", "score": 100, "completed": True},
            ]
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])
        self.assertEqual(response.data["transaction_outcome"], "failed")
        self.assertIn("duplicate_entries", response.data["validation_failures"])
        self.assertEqual(LessonProgress.objects.count(), 0)

    def test_malformed_request_rejected(self):
        self.client.force_authenticate(user=self.user)
        payload = {"lessons": [{"invalid_key": "lesson-1"}]}
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])
        self.assertEqual(response.data["transaction_outcome"], "failed")
