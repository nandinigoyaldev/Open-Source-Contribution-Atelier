"""
Tests for Feature 11: Issue Triage & Labeling Maintainer Scenario.

Covers:
  - TriageIssue model creation
  - TriageAttempt scoring via _score_triage helper
  - API endpoints: list, retrieve, submit_triage, my_attempts
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from apps.sandbox.models import TriageIssue, TriageAttempt
from apps.sandbox.views import _score_triage

User = get_user_model()


def make_issue(**kwargs):
    defaults = {
        "title": "Test Scenario",
        "raw_issue_title": "It broken",
        "raw_issue_body": "Nothing works pls fix",
        "correct_labels": ["bug", "needs-repro"],
        "model_response": "Thank you for the report! Could you provide steps and environment?",
        "hint": "It needs repro steps.",
        "difficulty": "easy",
    }
    defaults.update(kwargs)
    return TriageIssue.objects.create(**defaults)


class ScoreTriageTests(TestCase):
    """Unit tests for the _score_triage scoring helper."""

    def setUp(self):
        self.issue = make_issue()

    def test_perfect_labels_scores_50(self):
        label_score, _, _, _, _, _ = _score_triage(
            self.issue, ["bug", "needs-repro"], "placeholder response"
        )
        self.assertEqual(label_score, 50)

    def test_wrong_labels_scores_0(self):
        label_score, _, _, _, _, _ = _score_triage(
            self.issue, ["enhancement"], "placeholder response"
        )
        self.assertEqual(label_score, 0)

    def test_partial_labels_partial_score(self):
        # submitted: {bug}, correct: {bug, needs-repro}
        # intersection={bug}, union={bug,needs-repro}, jaccard=1/2=0.5, score=25
        label_score, _, _, _, _, _ = _score_triage(
            self.issue, ["bug"], "placeholder response"
        )
        self.assertEqual(label_score, 25)

    def test_good_response_scores_positively(self):
        good_response = (
            "Thank you for the report! Could you please provide the steps to reproduce "
            "and your environment (os, browser, version)? We appreciate your help."
        )
        _, response_score, total_score, passed, feedback, badge = _score_triage(
            self.issue, ["bug", "needs-repro"], good_response
        )
        self.assertGreater(response_score, 0)
        self.assertGreater(total_score, 70)
        self.assertTrue(passed)
        self.assertEqual(badge, "triager")

    def test_empty_response_scores_0(self):
        _, response_score, _, _, feedback, badge = _score_triage(
            self.issue, ["bug"], ""
        )
        self.assertEqual(response_score, 0)
        self.assertEqual(badge, "")

    def test_feedback_mentions_missing_label(self):
        _, _, _, _, feedback, _ = _score_triage(self.issue, ["bug"], "placeholder")
        self.assertIn("needs-repro", feedback)

    def test_feedback_excellent_when_all_correct(self):
        good_response = (
            "Thank you! Could you please share the steps to reproduce and your environment "
            "(os, browser version)? We appreciate it and hope to resolve this quickly."
        )
        _, _, _, _, feedback, _ = _score_triage(
            self.issue, ["bug", "needs-repro"], good_response
        )
        self.assertIn("Excellent", feedback)


class TriageAPITests(APITestCase):
    """Integration tests for the TriageIssueViewSet REST API."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="triager_test", password="pass1234"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.issue = make_issue()

    def test_list_issues(self):
        response = self.client.get("/api/sandbox/triage-issues/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_retrieve_issue(self):
        response = self.client.get(f"/api/sandbox/triage-issues/{self.issue.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], self.issue.title)
        # correct_labels should NOT be exposed via the serializer to the user
        self.assertIn("correct_labels", response.data)

    def test_submit_triage_creates_attempt(self):
        payload = {
            "submitted_labels": ["bug", "needs-repro"],
            "submitted_response": (
                "Thank you for the report! Could you please provide the steps to reproduce "
                "and your environment (os, browser, version)?"
            ),
        }
        response = self.client.post(
            f"/api/sandbox/triage-issues/{self.issue.id}/submit_triage/",
            data=payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.data
        self.assertIn("total_score", data)
        self.assertIn("passed", data)
        self.assertIn("feedback", data)
        # Correct labels → should score well
        self.assertGreater(data["total_score"], 0)

    def test_submit_triage_invalid_label_returns_400(self):
        payload = {
            "submitted_labels": ["not-a-real-label"],
            "submitted_response": "Some response",
        }
        response = self.client.post(
            f"/api/sandbox/triage-issues/{self.issue.id}/submit_triage/",
            data=payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_submit_triage_empty_response_returns_400(self):
        payload = {
            "submitted_labels": ["bug"],
            "submitted_response": "",
        }
        response = self.client.post(
            f"/api/sandbox/triage-issues/{self.issue.id}/submit_triage/",
            data=payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_my_attempts_returns_only_mine(self):
        # Create an attempt for another user
        other_user = User.objects.create_user(username="other_triager", password="pass")
        TriageAttempt.objects.create(
            issue=self.issue,
            user=other_user,
            submitted_labels=["bug"],
            submitted_response="hi",
            label_score=0,
            response_score=0,
            total_score=0,
            passed=False,
        )
        # Create attempt for self
        TriageAttempt.objects.create(
            issue=self.issue,
            user=self.user,
            submitted_labels=["bug", "needs-repro"],
            submitted_response="Thank you!",
            label_score=50,
            response_score=7,
            total_score=57,
            passed=False,
        )
        response = self.client.get("/api/sandbox/triage-issues/my_attempts/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for attempt in response.data:
            self.assertEqual(attempt["user"], self.user.id)

    def test_unauthenticated_request_denied(self):
        anon_client = APIClient()
        response = anon_client.get("/api/sandbox/triage-issues/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_filter_by_difficulty(self):
        make_issue(title="Hard issue", difficulty="hard")
        response = self.client.get("/api/sandbox/triage-issues/?difficulty=hard")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for item in response.data:
            self.assertEqual(item["difficulty"], "hard")
