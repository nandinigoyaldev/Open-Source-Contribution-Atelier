import uuid

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.content.models import Lesson

from .models import Certificate, LessonProgress, QuizAttempt

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

# Override REST_FRAMEWORK to strip the default throttle *rates* that the
# CertificateVerificationThrottle uses.  The view's throttle_classes list
# still points at CertificateVerificationThrottle, but by clearing its cache
# in setUp we avoid cross-test bleed.  For tests that need to make many
# requests to the rate-limited endpoint we also call cache.clear() before
# each request so the in-memory counter resets.
#
# IMPORTANT: we keep the sandbox-specific rates intact so that the existing
# sandbox throttle test suite (`test_sandbox_throttle.py`) is not broken by
# the class-level override.
NO_THROTTLE_SETTINGS = {
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {
        # These are required by the sandbox throttle tests.
        "sandbox_anon": "10/minute",
        "sandbox_user": "10/minute",
        "help_request": "5/hour",
    },
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}


def _clear_throttle_cache():
    """Wipe the entire cache so DRF throttle counters reset between tests."""
    cache.clear()


# ---------------------------------------------------------------------------
# CertificateVerificationView  (public – GET /api/progress/verify/<hash>/)
# ---------------------------------------------------------------------------


@override_settings(REST_FRAMEWORK=NO_THROTTLE_SETTINGS)
class CertificateVerificationTests(APITestCase):
    """Tests for the public certificate verification endpoint."""

    def setUp(self):
        _clear_throttle_cache()
        self.user = User.objects.create_user(
            username="testuser",
            first_name="Test",
            last_name="User",
            password="password123",
        )
        self.certificate = Certificate.objects.create(
            user=self.user,
            course_name="Test Course",
        )
        self.url = reverse(
            "verify-certificate",
            kwargs={"hash": self.certificate.verification_hash},
        )
        self.invalid_url = reverse(
            "verify-certificate",
            kwargs={"hash": "invalid-hash-123"},
        )

    def tearDown(self):
        _clear_throttle_cache()

    # -- Happy path -----------------------------------------------------------

    def test_verify_valid_certificate_returns_200(self):
        """A valid hash returns HTTP 200 with is_valid=True."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_valid"])

    def test_verify_valid_certificate_learner_name_full_name(self):
        """Learner name prefers full name when first_name + last_name are set."""
        response = self.client.get(self.url)
        self.assertEqual(response.data["certificate"]["learner_name"], "Test User")

    def test_verify_valid_certificate_learner_name_falls_back_to_username(self):
        """Learner name falls back to username when no full name is set."""
        user_no_name = User.objects.create_user(username="noname", password="pass")
        cert = Certificate.objects.create(user=user_no_name)
        url = reverse("verify-certificate", kwargs={"hash": cert.verification_hash})
        response = self.client.get(url)
        self.assertEqual(response.data["certificate"]["learner_name"], "noname")

    def test_verify_valid_certificate_course_name(self):
        """Response contains the correct course name."""
        response = self.client.get(self.url)
        self.assertEqual(response.data["certificate"]["course_name"], "Test Course")

    def test_verify_valid_certificate_hash_in_response(self):
        """Response contains the verification hash that matches the certificate."""
        response = self.client.get(self.url)
        self.assertEqual(
            response.data["certificate"]["verification_hash"],
            str(self.certificate.verification_hash),
        )

    def test_verify_valid_certificate_is_active_true(self):
        """Response includes is_active=True for an active certificate."""
        response = self.client.get(self.url)
        self.assertTrue(response.data["certificate"]["is_active"])

    def test_verify_valid_certificate_issued_at_present(self):
        """Response includes a non-null issued_at timestamp."""
        response = self.client.get(self.url)
        self.assertIn("issued_at", response.data["certificate"])
        self.assertIsNotNone(response.data["certificate"]["issued_at"])

    def test_verify_valid_certificate_no_auth_required(self):
        """Endpoint is accessible without any authentication credentials."""
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # -- Invalid hash ---------------------------------------------------------

    def test_verify_invalid_certificate_returns_404(self):
        """An invalid or fake hash returns HTTP 404."""
        response = self.client.get(self.invalid_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_verify_invalid_certificate_is_valid_false(self):
        """Response body contains is_valid=False for an invalid hash."""
        response = self.client.get(self.invalid_url)
        self.assertFalse(response.data["is_valid"])

    def test_verify_invalid_certificate_has_error_field(self):
        """Response body contains a string 'error' key for an invalid hash."""
        response = self.client.get(self.invalid_url)
        self.assertIn("error", response.data)
        self.assertIsInstance(response.data["error"], str)

    def test_verify_random_uuid_hash_not_found(self):
        """A syntactically valid UUID that doesn't exist in DB returns 404."""
        random_hash = str(uuid.uuid4())
        url = reverse("verify-certificate", kwargs={"hash": random_hash})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(response.data["is_valid"])

    # -- Revoked certificate --------------------------------------------------

    def test_verify_revoked_certificate_returns_200(self):
        """A revoked (is_active=False) certificate still returns HTTP 200."""
        self.certificate.is_active = False
        self.certificate.save()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_verify_revoked_certificate_is_valid_false(self):
        """A revoked certificate response has is_valid=False."""
        self.certificate.is_active = False
        self.certificate.save()
        response = self.client.get(self.url)
        self.assertFalse(response.data["is_valid"])

    def test_verify_revoked_certificate_error_mentions_revoked(self):
        """The error message for a revoked certificate contains the word 'revoked'."""
        self.certificate.is_active = False
        self.certificate.save()
        response = self.client.get(self.url)
        self.assertIn("revoked", response.data["error"])

    def test_verify_revoked_certificate_data_still_present(self):
        """Even a revoked certificate response includes the 'certificate' payload."""
        self.certificate.is_active = False
        self.certificate.save()
        response = self.client.get(self.url)
        self.assertIn("certificate", response.data)
        self.assertEqual(
            response.data["certificate"]["verification_hash"],
            str(self.certificate.verification_hash),
        )

    def test_verify_revoked_certificate_is_active_false(self):
        """The is_active field in the payload is False for a revoked certificate."""
        self.certificate.is_active = False
        self.certificate.save()
        response = self.client.get(self.url)
        self.assertFalse(response.data["certificate"]["is_active"])


# ---------------------------------------------------------------------------
# MyCertificateView  (authenticated – GET /api/progress/certificate/)
# ---------------------------------------------------------------------------


@override_settings(REST_FRAMEWORK=NO_THROTTLE_SETTINGS)
class MyCertificateTests(APITestCase):
    """Tests for the authenticated certificate generation/retrieval endpoint."""

    def setUp(self):
        _clear_throttle_cache()
        self.user = User.objects.create_user(username="student", password="password123")
        self.url = reverse("my-certificate")

    def tearDown(self):
        _clear_throttle_cache()

    # -- Authentication guard -------------------------------------------------

    def test_get_certificate_unauthenticated_denied(self):
        """Anonymous users are denied access (403 or 401 depending on auth backend)."""
        response = self.client.get(self.url)
        # JWT auth with IsAuthenticated returns 403 when no token is provided
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    # -- Not eligible ---------------------------------------------------------

    def test_get_certificate_not_eligible_returns_400(self):
        """Returns 400 when the user hasn't completed all lessons."""
        self.client.force_authenticate(user=self.user)
        Lesson.objects.create(slug="lesson-1", title="Lesson 1", difficulty="beginner")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_certificate_not_eligible_has_false_flag(self):
        """Response has has_certificate=False when not eligible."""
        self.client.force_authenticate(user=self.user)
        Lesson.objects.create(slug="lesson-1", title="Lesson 1", difficulty="beginner")
        response = self.client.get(self.url)
        self.assertFalse(response.data["has_certificate"])

    def test_get_certificate_partially_completed_not_eligible(self):
        """Partial completion (some lessons incomplete) does not generate a certificate."""
        self.client.force_authenticate(user=self.user)
        lesson1 = Lesson.objects.create(slug="l1", title="L1", difficulty="beginner")
        lesson2 = Lesson.objects.create(slug="l2", title="L2", difficulty="beginner")
        # Only one of two lessons completed
        LessonProgress.objects.create(user=self.user, lesson=lesson1, completed=True)
        LessonProgress.objects.create(user=self.user, lesson=lesson2, completed=False)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["has_certificate"])

    def test_get_certificate_no_lessons_not_eligible(self):
        """Returns 400 when there are no lessons in the system at all."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # -- Eligible – auto-generation -------------------------------------------

    def _create_and_complete_lessons(self, count=2):
        """Helper: create `count` lessons and mark them all complete for self.user."""
        lessons = []
        for i in range(1, count + 1):
            lesson = Lesson.objects.create(
                slug=f"lesson-{i}", title=f"Lesson {i}", difficulty="beginner"
            )
            LessonProgress.objects.create(user=self.user, lesson=lesson, completed=True)
            lessons.append(lesson)
        return lessons

    def test_get_certificate_eligible_first_request_returns_201(self):
        """First call after full completion returns HTTP 201 (created)."""
        self.client.force_authenticate(user=self.user)
        self._create_and_complete_lessons()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_get_certificate_eligible_has_certificate_true(self):
        """Response has has_certificate=True when eligible."""
        self.client.force_authenticate(user=self.user)
        self._create_and_complete_lessons()
        response = self.client.get(self.url)
        self.assertTrue(response.data["has_certificate"])

    def test_get_certificate_eligible_returns_hash(self):
        """Generated certificate includes a non-empty verification_hash."""
        self.client.force_authenticate(user=self.user)
        self._create_and_complete_lessons()
        response = self.client.get(self.url)
        cert_hash = response.data["certificate"]["verification_hash"]
        self.assertTrue(cert_hash)

    def test_get_certificate_eligible_hash_is_unique_per_user(self):
        """Two different users receive different verification hashes."""
        self.client.force_authenticate(user=self.user)
        self._create_and_complete_lessons()
        response1 = self.client.get(self.url)
        hash1 = response1.data["certificate"]["verification_hash"]

        user2 = User.objects.create_user(username="student2", password="pass")
        self.client.force_authenticate(user=user2)
        for lesson in Lesson.objects.all():
            LessonProgress.objects.create(user=user2, lesson=lesson, completed=True)
        response2 = self.client.get(self.url)
        hash2 = response2.data["certificate"]["verification_hash"]

        self.assertNotEqual(hash1, hash2)

    def test_get_certificate_second_request_returns_200(self):
        """Subsequent calls return HTTP 200 (idempotent – already exists)."""
        self.client.force_authenticate(user=self.user)
        self._create_and_complete_lessons()
        self.client.get(self.url)  # first – creates
        response = self.client.get(self.url)  # second – retrieves
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_certificate_idempotent_same_hash(self):
        """Repeated calls always return the same verification hash."""
        self.client.force_authenticate(user=self.user)
        self._create_and_complete_lessons()
        r1 = self.client.get(self.url)
        r2 = self.client.get(self.url)
        self.assertEqual(
            r1.data["certificate"]["verification_hash"],
            r2.data["certificate"]["verification_hash"],
        )

    def test_get_certificate_creates_db_record(self):
        """After the first eligible call a Certificate DB row exists for the user."""
        self.client.force_authenticate(user=self.user)
        self._create_and_complete_lessons()
        self.assertEqual(Certificate.objects.filter(user=self.user).count(), 0)
        self.client.get(self.url)
        self.assertEqual(Certificate.objects.filter(user=self.user).count(), 1)

    def test_get_certificate_does_not_duplicate_db_records(self):
        """Multiple requests do not create duplicate Certificate rows."""
        self.client.force_authenticate(user=self.user)
        self._create_and_complete_lessons()
        self.client.get(self.url)
        self.client.get(self.url)
        self.client.get(self.url)
        self.assertEqual(Certificate.objects.filter(user=self.user).count(), 1)

    def test_get_certificate_generated_is_publicly_verifiable(self):
        """A certificate generated via MyCertificateView is verifiable on the public endpoint."""
        self.client.force_authenticate(user=self.user)
        self._create_and_complete_lessons()
        create_resp = self.client.get(self.url)
        cert_hash = create_resp.data["certificate"]["verification_hash"]

        # Verify via the public endpoint (no auth needed)
        self.client.force_authenticate(user=None)
        _clear_throttle_cache()
        verify_url = reverse("verify-certificate", kwargs={"hash": cert_hash})
        verify_resp = self.client.get(verify_url)
        self.assertEqual(verify_resp.status_code, status.HTTP_200_OK)
        self.assertTrue(verify_resp.data["is_valid"])

    # -- Pre-existing certificate ---------------------------------------------

    def test_get_certificate_already_has_one_returns_200(self):
        """If a certificate already exists for the user, returns 200 immediately."""
        Certificate.objects.create(user=self.user)
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["has_certificate"])


# ---------------------------------------------------------------------------
# RecommendationsView  (authenticated – GET /api/progress/recommendations/)
# ---------------------------------------------------------------------------


class RecommendationsTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="learner", password="password123")
        self.url = reverse("recommendations")

    def test_unauthenticated_returns_403(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_no_completed_lessons_returns_all_uncompleted_in_first_category(self):
        self.client.force_authenticate(user=self.user)
        # Create some lessons in a few categories
        l1 = Lesson.objects.create(slug="c1-1", title="C1 L1", category="cat1", order=1)
        l2 = Lesson.objects.create(slug="c1-2", title="C1 L2", category="cat1", order=2)
        l3 = Lesson.objects.create(slug="c2-1", title="C2 L1", category="cat2", order=3)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # 0 completion rate for all. "cat1" has lower min_order (1) so it should be the top category.
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]["slug"], "c1-1")

    def test_prioritizes_started_but_incomplete_categories(self):
        self.client.force_authenticate(user=self.user)
        # cat1: 1/3 completed = 33%
        l1_1 = Lesson.objects.create(
            slug="c1-1", title="C1 L1", category="cat1", order=1
        )
        l1_2 = Lesson.objects.create(
            slug="c1-2", title="C1 L2", category="cat1", order=2
        )
        l1_3 = Lesson.objects.create(
            slug="c1-3", title="C1 L3", category="cat1", order=3
        )

        # cat2: 1/2 completed = 50%
        l2_1 = Lesson.objects.create(
            slug="c2-1", title="C2 L1", category="cat2", order=4
        )
        l2_2 = Lesson.objects.create(
            slug="c2-2", title="C2 L2", category="cat2", order=5
        )

        LessonProgress.objects.create(user=self.user, lesson=l1_1, completed=True)
        LessonProgress.objects.create(user=self.user, lesson=l2_1, completed=True)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # cat2 has 50% completion rate, which is higher than cat1's 33%.
        # Should recommend uncompleted lessons from cat2.
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["slug"], "c2-2")

    def test_ignores_fully_completed_categories(self):
        self.client.force_authenticate(user=self.user)
        # cat1: 1/1 completed = 100%
        l1_1 = Lesson.objects.create(
            slug="c1-1", title="C1 L1", category="cat1", order=1
        )
        # cat2: 0/1 completed = 0%
        l2_1 = Lesson.objects.create(
            slug="c2-1", title="C2 L1", category="cat2", order=2
        )

        LessonProgress.objects.create(user=self.user, lesson=l1_1, completed=True)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["slug"], "c2-1")

    def test_all_categories_completed_returns_empty(self):
        self.client.force_authenticate(user=self.user)
        l1 = Lesson.objects.create(slug="c1-1", title="C1 L1", category="cat1", order=1)
        LessonProgress.objects.create(user=self.user, lesson=l1, completed=True)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)


# ---------------------------------------------------------------------------
# QuizAttemptView  (authenticated – POST/GET /api/progress/quiz-attempts/)
# ---------------------------------------------------------------------------


class QuizAttemptTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="learner", password="password123")
        self.url = reverse("quiz-attempts")

    def test_unauthenticated_returns_401(self):
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_post_valid_data_creates_attempt(self):
        self.client.force_authenticate(user=self.user)
        data = {
            "question_id": "q1",
            "question_text": "What is 2+2?",
            "selected_answer": "4",
            "correct_answer": "4",
            "is_correct": True,
            "time_taken_seconds": 15,
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["question_id"], "q1")
        self.assertTrue(response.data["is_correct"])

        # Verify DB
        self.assertEqual(QuizAttempt.objects.count(), 1)
        attempt = QuizAttempt.objects.first()
        self.assertEqual(attempt.user, self.user)
        self.assertEqual(attempt.question_id, "q1")

    def test_post_missing_required_fields_returns_400(self):
        self.client.force_authenticate(user=self.user)
        # Missing question_id, selected_answer, correct_answer
        data = {"is_correct": True}
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("question_id", response.data)
        self.assertIn("selected_answer", response.data)
        self.assertIn("correct_answer", response.data)
        self.assertEqual(QuizAttempt.objects.count(), 0)

    def test_get_quiz_attempts_list(self):
        self.client.force_authenticate(user=self.user)
        QuizAttempt.objects.create(
            user=self.user,
            question_id="q1",
            question_text="q1",
            selected_answer="a",
            correct_answer="a",
            is_correct=True,
        )
        QuizAttempt.objects.create(
            user=self.user,
            question_id="q2",
            question_text="q2",
            selected_answer="b",
            correct_answer="c",
            is_correct=False,
        )

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_attempts"], 2)
        self.assertEqual(response.data["correct"], 1)
        self.assertEqual(response.data["incorrect"], 1)
        self.assertEqual(response.data["accuracy_percent"], 50.0)
        self.assertEqual(len(response.data["attempts"]), 2)

    def test_get_quiz_attempts_filter_by_question_id(self):
        self.client.force_authenticate(user=self.user)
        QuizAttempt.objects.create(
            user=self.user,
            question_id="q1",
            question_text="q1",
            selected_answer="a",
            correct_answer="a",
            is_correct=True,
        )
        QuizAttempt.objects.create(
            user=self.user,
            question_id="q2",
            question_text="q2",
            selected_answer="b",
            correct_answer="c",
            is_correct=False,
        )

        response = self.client.get(f"{self.url}?question_id=q1")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_attempts"], 1)
        self.assertEqual(len(response.data["attempts"]), 1)
        self.assertEqual(response.data["attempts"][0]["question_id"], "q1")


class PeerReviewTests(APITestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username="user1", password="password123")
        self.user2 = User.objects.create_user(username="user2", password="password123")
        self.code_submissions_url = reverse("code-submissions")

    def test_submit_code(self):
        self.client.force_authenticate(user=self.user1)
        data = {
            "title": "My solution",
            "code_snippet": "print('hello')",
            "description": "Please review",
        }
        response = self.client.post(self.code_submissions_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "My solution")

    def test_list_pending_submissions_excludes_own(self):
        from .models import CodeSubmission

        CodeSubmission.objects.create(
            user=self.user1, title="user1 code", code_snippet="code"
        )
        CodeSubmission.objects.create(
            user=self.user2, title="user2 code", code_snippet="code"
        )

        self.client.force_authenticate(user=self.user1)
        response = self.client.get(self.code_submissions_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["username"], "user2")

    def test_submit_review(self):
        from .models import CodeSubmission

        submission = CodeSubmission.objects.create(
            user=self.user1, title="user1 code", code_snippet="code"
        )

        self.client.force_authenticate(user=self.user2)
        url = reverse("peer-reviews", kwargs={"submission_id": submission.id})
        data = {"feedback": "Looks good!", "rating": 5}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["points_earned"], 10)

        submission.refresh_from_db()
        self.assertEqual(submission.status, "reviewed")

    def test_cannot_review_own_submission(self):
        from .models import CodeSubmission

        submission = CodeSubmission.objects.create(
            user=self.user1, title="user1 code", code_snippet="code"
        )

        self.client.force_authenticate(user=self.user1)
        url = reverse("peer-reviews", kwargs={"submission_id": submission.id})
        data = {"feedback": "Looks good!", "rating": 5}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Cannot review your own", response.data["error"])
