"""
Tests for submission idempotency across quiz, code submissions, and progress endpoints (#3357).
"""

import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.deduplication.idempotency import idempotent
from apps.deduplication.models import IdempotencyRecord
from apps.progress.models import CodeSubmission
from apps.progress.views import CodeSubmissionView, ReadingProgressView

User = get_user_model()


class SubmissionIdempotencyIntegrationTest(TestCase):
    def setUp(self):
        cache.clear()
        self.factory = APIRequestFactory()
        self.user1 = User.objects.create_user(
            username="learner_one",
            email="learner1@example.com",
            password="securepassword123",
        )
        self.user2 = User.objects.create_user(
            username="learner_two",
            email="learner2@example.com",
            password="securepassword123",
        )

    def test_quiz_attempt_idempotency_replay_and_conflict(self):
        """
        Replaying a quiz attempt with the same idempotency key returns cached result.
        Reusing the same key with a different answer payload returns 409 Conflict.
        """
        call_tracker = {"executions": 0}

        from rest_framework.views import APIView

        class SimulatedQuizView(APIView):
            @idempotent
            def post(self, request):
                call_tracker["executions"] += 1
                answer = request.data.get("selected_option")
                return Response(
                    {
                        "is_correct": answer == "B",
                        "earned_xp": 25 if answer == "B" else 0,
                        "attempt_number": call_tracker["executions"],
                    },
                    status=status.HTTP_200_OK,
                )

        view = SimulatedQuizView.as_view()

        payload = {"question_id": 42, "selected_option": "B", "nonce": "safe-nonce-xyz"}
        req1 = self.factory.post(
            "/api/v1/progress/quiz-attempts/",
            data=payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="client-quiz-sub-101",
        )
        force_authenticate(req1, user=self.user1)

        # First attempt: processes normally
        resp1 = view(req1)
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)
        self.assertEqual(resp1.data["is_correct"], True)
        self.assertEqual(resp1.data["earned_xp"], 25)
        self.assertEqual(call_tracker["executions"], 1)

        # Replay attempt: network reconnect / retry returns cached response
        req2 = self.factory.post(
            "/api/v1/progress/quiz-attempts/",
            data=payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="client-quiz-sub-101",
        )
        force_authenticate(req2, user=self.user1)

        resp2 = view(req2)
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(resp2.data["earned_xp"], 25)
        self.assertEqual(resp2.headers.get("Idempotency-Replay"), "true")
        self.assertEqual(
            call_tracker["executions"],
            1,
            "Underlying calculation must not re-run on replay",
        )

        # Conflict: client reuses same key with different answer payload
        conflict_payload = {
            "question_id": 42,
            "selected_option": "C",
            "nonce": "safe-nonce-xyz",
        }
        req3 = self.factory.post(
            "/api/v1/progress/quiz-attempts/",
            data=conflict_payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="client-quiz-sub-101",
        )
        force_authenticate(req3, user=self.user1)

        resp3 = view(req3)
        self.assertEqual(resp3.status_code, status.HTTP_409_CONFLICT)
        self.assertIn(
            "already exists with a different request body", resp3.data["error"]
        )

    def test_offline_queue_client_mutation_id_deduplication(self):
        """
        Offline queue retries transmitting `client_mutation_id` in request body
        safely deduplicate without duplicate record creation.
        """
        payload = {
            "client_mutation_id": "offline-sync-uuid-999",
            "code": "def solution(): return 42",
            "language": "python",
        }

        view = CodeSubmissionView.as_view()

        req1 = self.factory.post(
            "/api/v1/progress/code-submissions/",
            data=payload,
            format="json",
        )
        req1.user = self.user1
        force_authenticate(req1, user=self.user1)

        with (
            patch(
                "apps.progress.serializers.CodeSubmissionSerializer.is_valid",
                return_value=True,
            ),
            patch(
                "apps.progress.serializers.CodeSubmissionSerializer.save"
            ) as mock_save,
        ):
            mock_submission = MagicMock(spec=CodeSubmission)
            mock_submission.id = 77
            mock_submission.exercise = None
            mock_save.return_value = mock_submission

            with patch(
                "apps.progress.serializers.CodeSubmissionSerializer.data",
                {"id": 77, "status": "pending_review"},
            ):
                resp1 = view(req1)
                self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)
                self.assertEqual(mock_save.call_count, 1)

                # Replay identical offline-queued request
                req2 = self.factory.post(
                    "/api/v1/progress/code-submissions/",
                    data=payload,
                    format="json",
                )
                req2.user = self.user1
                force_authenticate(req2, user=self.user1)

                resp2 = view(req2)
                self.assertEqual(resp2.status_code, status.HTTP_201_CREATED)
                self.assertEqual(resp2.headers.get("Idempotency-Replay"), "true")
                self.assertEqual(
                    mock_save.call_count, 1, "Save must NOT be called again on replay"
                )

    def test_cross_user_idempotency_isolation(self):
        """
        Users submitting with the same client idempotency key are strictly isolated
        and do not leak cached responses or collide with each other.
        """
        call_counts = {"learner_one": 0, "learner_two": 0}

        @idempotent
        def progress_view(view, request):
            uid = request.user.username
            call_counts[uid] += 1
            return Response({"user": uid, "score": 100}, status=status.HTTP_200_OK)

        key = "shared-uuid-key-555"

        # User 1 sends request
        req1 = self.factory.post(
            "/api/v1/progress/bulk-sync/",
            data={"lessons": [{"id": 1, "completed": True}]},
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )
        req1.user = self.user1
        force_authenticate(req1, user=self.user1)
        resp1 = progress_view(MagicMock(), req1)
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)
        self.assertEqual(resp1.data["user"], "learner_one")
        self.assertEqual(call_counts["learner_one"], 1)

        # User 2 sends request with identical key
        req2 = self.factory.post(
            "/api/v1/progress/bulk-sync/",
            data={"lessons": [{"id": 2, "completed": True}]},
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )
        req2.user = self.user2
        force_authenticate(req2, user=self.user2)
        resp2 = progress_view(MagicMock(), req2)
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(resp2.data["user"], "learner_two")
        self.assertEqual(call_counts["learner_two"], 1)

    def test_reading_progress_idempotency_replay(self):
        """
        Reading progress position sync returns cached response when replaying.
        """
        view = ReadingProgressView.as_view()
        payload = {"lesson": "git-basics", "progress": 85}

        req1 = self.factory.post(
            "/api/v1/progress/reading-position/",
            data=payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="read-pos-001",
        )
        req1.user = self.user1
        force_authenticate(req1, user=self.user1)

        resp1 = view(req1)
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)
        self.assertEqual(resp1.data["status"], "success")

        # Replay
        req2 = self.factory.post(
            "/api/v1/progress/reading-position/",
            data=payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="read-pos-001",
        )
        req2.user = self.user1
        force_authenticate(req2, user=self.user1)

        resp2 = view(req2)
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(resp2.headers.get("Idempotency-Replay"), "true")
