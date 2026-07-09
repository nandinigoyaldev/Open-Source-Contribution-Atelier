from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from rest_framework.test import APIClient
from rest_framework import status
from apps.moderation.models import ContentReport
from apps.progress.models import CodeSubmission, PeerReview

User = get_user_model()


class ModerationWorkflowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", password="password123"
        )
        self.admin = User.objects.create_superuser(
            username="adminuser", password="password123"
        )

        self.submission = CodeSubmission.objects.create(
            user=self.user, title="Test Submission", code_snippet="print('hello')"
        )
        self.review = PeerReview.objects.create(
            submission=self.submission,
            reviewer=self.user,
            feedback="This is spam",
            rating=1,
        )
        self.review_ct = ContentType.objects.get_for_model(PeerReview)

    def test_create_report(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/moderation/reports/",
            {
                "content_type_app": "progress",
                "content_type_model": "peerreview",
                "object_id": self.review.id,
                "category": "SPAM",
                "description": "I don't like this",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ContentReport.objects.count(), 1)

    def test_admin_approve_report_hides_content(self):
        report = ContentReport.objects.create(
            reporter=self.user,
            content_type=self.review_ct,
            object_id=self.review.id,
            category=ContentReport.Category.SPAM,
        )
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            f"/api/moderation/reports/{report.id}/action/", {"status": "APPROVED"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        report.refresh_from_db()
        self.assertEqual(report.status, "APPROVED")
        self.assertEqual(report.action_taken, "HIDDEN")

        self.review.refresh_from_db()
        self.assertTrue(self.review.is_hidden)

    def test_duplicate_report_rejected(self):
        self.client.force_authenticate(user=self.user)
        # Create first report
        self.client.post(
            "/api/moderation/reports/",
            {
                "content_type_app": "progress",
                "content_type_model": "peerreview",
                "object_id": self.review.id,
                "category": "SPAM",
                "description": "I don't like this",
            },
        )
        # Attempt second report
        response2 = self.client.post(
            "/api/moderation/reports/",
            {
                "content_type_app": "progress",
                "content_type_model": "peerreview",
                "object_id": self.review.id,
                "category": "HARASSMENT",
                "description": "And another thing",
            },
        )
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_content_type(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/moderation/reports/",
            {
                "content_type_app": "invalidapp",
                "content_type_model": "invalidmodel",
                "object_id": 999,
                "category": "SPAM",
                "description": "Invalid report",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_admin_cannot_action_report(self):
        report = ContentReport.objects.create(
            reporter=self.user,
            content_type=self.review_ct,
            object_id=self.review.id,
            category=ContentReport.Category.SPAM,
        )
        # A normal user (self.user) tries to approve
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            f"/api/moderation/reports/{report.id}/action/", {"status": "APPROVED"}
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_report_dismissal(self):
        report = ContentReport.objects.create(
            reporter=self.user,
            content_type=self.review_ct,
            object_id=self.review.id,
            category=ContentReport.Category.SPAM,
        )
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            f"/api/moderation/reports/{report.id}/action/", {"status": "DISMISSED"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        report.refresh_from_db()
        self.assertEqual(report.status, "DISMISSED")
        self.assertEqual(report.action_taken, "NONE")

        self.review.refresh_from_db()
        self.assertFalse(self.review.is_hidden)
