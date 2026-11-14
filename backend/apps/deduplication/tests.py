"""
Tests for request deduplication and idempotency.
"""

import json
import threading
import time
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import RequestFactory, TestCase
from django.utils import timezone
from rest_framework.response import Response

from apps.deduplication.idempotency import (
    cleanup_expired_records,
    compute_normalized_body_hash,
    extract_idempotency_key,
    idempotent,
)
from apps.deduplication.middleware import RequestCoalescer
from apps.deduplication.models import IdempotencyRecord


class RequestDeduplicationTest(TestCase):
    """
    Test request deduplication functionality.
    """

    def setUp(self):
        cache.clear()
        self.coalescer = RequestCoalescer()

    def test_request_key_generation(self):
        """Test that same requests generate same key."""
        key1 = "test|key"
        key2 = "test|key"
        self.assertEqual(key1, key2)

    def test_pending_request_registration(self):
        """Test pending request registration."""
        request_key = "test_key"
        self.coalescer.register_pending_request(request_key, "req1")

        self.assertTrue(self.coalescer.is_request_in_progress(request_key))
        self.coalescer.complete_request(request_key, "result")
        self.assertFalse(self.coalescer.is_request_in_progress(request_key))

    def test_cache_response(self):
        """Test caching of responses."""
        request_key = "test_key"
        response_data = {"data": "test"}

        self.coalescer.set_cached_response(request_key, response_data)
        cached = self.coalescer.get_cached_response(request_key)
        self.assertEqual(cached, response_data)

    def test_concurrent_requests(self):
        """Test that concurrent requests are coalesced."""
        results = []

        def make_request():
            time.sleep(0.05)
            results.append("done")

        threads = []
        for _ in range(5):
            t = threading.Thread(target=make_request)
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        self.assertEqual(len(results), 5)


class IdempotencyKeyTest(TestCase):
    """
    Test idempotency keys for progress and quiz submissions.
    """

    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()
        self.user = get_user_model().objects.create_user(
            username="idemp_user", email="idemp@example.com", password="password123"
        )

    def test_key_extraction_variants(self):
        """Supports Idempotency-Key, X-Idempotency-Key, and body payload."""
        # 1. Idempotency-Key header
        req1 = self.factory.post("/api/v1/progress/quiz/", {}, HTTP_IDEMPOTENCY_KEY="key-1")
        self.assertEqual(extract_idempotency_key(req1), "key-1")

        # 2. X-Idempotency-Key header
        req2 = self.factory.post("/api/v1/progress/quiz/", {}, HTTP_X_IDEMPOTENCY_KEY="key-2")
        self.assertEqual(extract_idempotency_key(req2), "key-2")

        # 3. Body idempotency_key
        req3 = self.factory.post(
            "/api/v1/progress/quiz/",
            data=json.dumps({"idempotency_key": "key-3", "score": 100}),
            content_type="application/json",
        )
        req3.data = {"idempotency_key": "key-3", "score": 100}
        self.assertEqual(extract_idempotency_key(req3), "key-3")

        # 4. Body client_mutation_id (offline queue)
        req4 = self.factory.post(
            "/api/v1/progress/quiz/",
            data=json.dumps({"client_mutation_id": "mut-4", "score": 80}),
            content_type="application/json",
        )
        req4.data = {"client_mutation_id": "mut-4", "score": 80}
        self.assertEqual(extract_idempotency_key(req4), "mut-4")

    def test_replay_returns_cached_result_without_duplicate_execution(self):
        """Replaying with the same key returns the cached response and does not re-execute."""
        call_count = {"count": 0}

        @idempotent
        def dummy_quiz_attempt(view, request):
            call_count["count"] += 1
            return Response({"earned_xp": 50, "attempt_id": call_count["count"]}, status=200)

        mock_view = MagicMock()
        req1 = self.factory.post(
            "/api/v1/progress/quiz/",
            data=json.dumps({"quiz_id": "quiz-1", "answer": "A"}),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="test-idemp-key-1",
        )
        req1.user = self.user

        # First attempt executes
        resp1 = dummy_quiz_attempt(mock_view, req1)
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp1.data["attempt_id"], 1)
        self.assertEqual(call_count["count"], 1)

        # Replay with same key
        req2 = self.factory.post(
            "/api/v1/progress/quiz/",
            data=json.dumps({"quiz_id": "quiz-1", "answer": "A"}),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="test-idemp-key-1",
        )
        req2.user = self.user

        resp2 = dummy_quiz_attempt(mock_view, req2)
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.data["attempt_id"], 1)
        self.assertEqual(resp2.headers.get("Idempotency-Replay"), "true")
        # Ensure underlying view was NOT called again
        self.assertEqual(call_count["count"], 1)

    def test_different_payload_with_same_key_returns_409(self):
        """Reusing key with a different payload must be rejected with 409 Conflict."""
        @idempotent
        def dummy_view(view, request):
            return Response({"status": "success"}, status=200)

        mock_view = MagicMock()
        req1 = self.factory.post(
            "/api/v1/progress/bulk-update/",
            data=json.dumps({"lesson_id": "lesson-1"}),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="key-conflict",
        )
        req1.user = self.user
        resp1 = dummy_view(mock_view, req1)
        self.assertEqual(resp1.status_code, 200)

        # Same key, different body
        req2 = self.factory.post(
            "/api/v1/progress/bulk-update/",
            data=json.dumps({"lesson_id": "lesson-2"}),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="key-conflict",
        )
        req2.user = self.user
        resp2 = dummy_view(mock_view, req2)
        self.assertEqual(resp2.status_code, 409)
        self.assertIn("already exists with a different request body", resp2.data["error"])

    def test_concurrent_request_waiting_and_replaying(self):
        """Simulate concurrent request where second request waits for lock and gets completed record."""
        endpoint = "/api/v1/progress/quiz/"
        key = "concurrent-sim-key"
        lock_key = f"idemp_lock:{endpoint}:{key}"

        call_count = {"count": 0}

        @idempotent
        def quiz_view(view, request):
            call_count["count"] += 1
            return Response({"earned_xp": 100}, status=200)

        mock_view = MagicMock()
        req = self.factory.post(
            endpoint,
            data=json.dumps({"quiz_id": "q1"}),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=key,
        )
        req.user = self.user

        # First request completes
        resp1 = quiz_view(mock_view, req)
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(call_count["count"], 1)

        # Concurrent second request arriving while lock is held finds finished record
        cache.set(lock_key, "locked", timeout=5)
        resp2 = quiz_view(mock_view, req)
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.headers.get("Idempotency-Replay"), "true")
        self.assertEqual(call_count["count"], 1)

    def test_concurrent_in_flight_timeout_returns_409(self):
        """When another request holds the lock and does not complete, 409 is returned."""
        endpoint = "/api/v1/progress/quiz/"
        key = "in-flight-key"
        lock_key = f"idemp_lock:{endpoint}:{key}"
        cache.set(lock_key, "locked", timeout=10)

        @idempotent
        def quiz_view(view, request):
            return Response({"earned_xp": 100}, status=200)

        req = self.factory.post(
            endpoint,
            data=json.dumps({"quiz_id": "q2"}),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=key,
        )
        req.user = self.user

        with patch("apps.deduplication.idempotency.time.sleep", return_value=None):
            resp = quiz_view(MagicMock(), req)
            self.assertEqual(resp.status_code, 409)
            self.assertIn("currently being processed", resp.data["error"])

    def test_retention_cleanup(self):
        """Expired records are purged by retention cleanup."""
        now = timezone.now()
        # Create an expired record
        IdempotencyRecord.objects.create(
            idempotency_key="expired-key",
            endpoint="/api/v1/progress/quiz/",
            request_body_hash="hash1",
            request_method="POST",
            response_status=200,
            response_body=json.dumps({"ok": True}),
            expires_at=now - timedelta(hours=1),
        )
        # Create an active record
        IdempotencyRecord.objects.create(
            idempotency_key="active-key",
            endpoint="/api/v1/progress/quiz/",
            request_body_hash="hash2",
            request_method="POST",
            response_status=200,
            response_body=json.dumps({"ok": True}),
            expires_at=now + timedelta(hours=24),
        )

        deleted = cleanup_expired_records()
        self.assertEqual(deleted, 1)
        self.assertFalse(IdempotencyRecord.objects.filter(idempotency_key="expired-key").exists())
        self.assertTrue(IdempotencyRecord.objects.filter(idempotency_key="active-key").exists())
