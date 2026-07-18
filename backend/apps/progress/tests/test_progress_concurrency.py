from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import close_old_connections
from django.test import TransactionTestCase, skipUnlessDBFeature
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.content.models import Lesson
from apps.progress.models import (
    LessonProgress,
    LessonProgressSync,
    XPEvent,
)
from apps.progress.views import MyProgressView


class ProgressConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.factory = APIRequestFactory()

        self.user = User.objects.create_user(
            username="concurrent-user",
            password="test-password",
        )

        self.lesson = Lesson.objects.create(
            title="Concurrency Lesson",
            slug="concurrency-lesson",
            summary="Test lesson",
            content="Test content",
            difficulty="beginner",
            organization=getattr(
                self.user,
                "organization",
                None,
            ),
        )

        # Create the row before concurrent requests.
        #
        # select_for_update() protects an existing progress row,
        # allowing concurrent updates to be serialized.
        self.progress = LessonProgress.objects.create(
            user=self.user,
            lesson=self.lesson,
            organization=getattr(
                self.user,
                "organization",
                None,
            ),
            completed=False,
            base_score=0,
            multiplier_applied=1.0,
            score=0,
        )

    def _post_progress(
        self,
        score,
        idempotency_key,
    ):
        close_old_connections()

        try:
            user = User.objects.get(pk=self.user.pk)

            request = self.factory.post(
                "/api/progress/my-progress/",
                {
                    "lesson_slug": self.lesson.slug,
                    "score": score,
                    "completed": True,
                    "idempotency_key": idempotency_key,
                },
                format="json",
            )

            force_authenticate(
                request,
                user=user,
            )

            response = MyProgressView.as_view()(request)

            return response.status_code

        finally:
            close_old_connections()

    @skipUnlessDBFeature("has_select_for_update")
    @patch("django_q.tasks.async_task")
    def test_concurrent_duplicate_idempotency_key_is_applied_once(
        self,
        mocked_task,
    ):
        """
        Concurrent requests using the same idempotency key must
        serialize progress mutation and apply XP only once.

        This test requires a database backend supporting
        SELECT ... FOR UPDATE, such as PostgreSQL.
        """
        idempotency_key = "same-concurrent-key"

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(
                    self._post_progress,
                    100,
                    idempotency_key,
                ),
                executor.submit(
                    self._post_progress,
                    100,
                    idempotency_key,
                ),
            ]

            statuses = [future.result() for future in futures]

        self.assertTrue(
            all(response_status in (200, 201) for response_status in statuses)
        )

        self.assertEqual(
            LessonProgress.objects.filter(
                user=self.user,
                lesson=self.lesson,
            ).count(),
            1,
        )

        progress = LessonProgress.objects.get(
            user=self.user,
            lesson=self.lesson,
        )

        self.assertEqual(
            progress.base_score,
            100,
        )

        self.assertEqual(
            progress.score,
            100,
        )

        self.assertTrue(
            progress.completed,
        )

        self.assertEqual(
            LessonProgressSync.objects.filter(
                user=self.user,
                lesson=self.lesson,
                idempotency_key=idempotency_key,
            ).count(),
            1,
        )

        self.assertEqual(
            XPEvent.objects.filter(
                user=self.user,
                source_type="lesson",
                source_id=self.lesson.id,
            ).count(),
            1,
        )
