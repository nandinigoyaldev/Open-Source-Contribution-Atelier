from unittest.mock import patch, MagicMock
from django.core import mail
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.notifications.tasks import send_bulk_email, send_notification_digests
from apps.notifications.models import NotificationPreference, Notification

User = get_user_model()


class SendBulkEmailTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="bulk_user",
            email="bulk_user@example.com",
            password="password123",
        )
        mail.outbox = []

    def test_send_bulk_email_invalid_payload(self):
        """Invalid payload or empty recipients should exit cleanly without sending emails."""
        send_bulk_email(None)
        send_bulk_email({})
        send_bulk_email({"recipients": []})
        self.assertEqual(len(mail.outbox), 0)

    @patch("apps.progress.services.pdf_report_service.PDFReportGenerator.generate")
    def test_weekly_progress_summary_with_xp(self, mock_pdf_generate):
        """Test weekly_progress_summary template with XP earned."""
        mock_pdf_generate.return_value = b"%PDF-1.4 Mock PDF Content"

        payload = {
            "template_id": "weekly_progress_summary",
            "recipients": [self.user.email],
            "data": {
                "username": self.user.username,
                "xp_earned": 150,
                "current_streak": 3,
                "lessons_completed": 2,
                "rank": 5,
                "start_date": "2026-07-01",
                "end_date": "2026-07-07",
            },
        }

        send_bulk_email(payload)

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertIn("150 XP this week", sent.subject)
        self.assertIn(self.user.email, sent.to)
        self.assertTrue(len(sent.attachments) > 0)
        attachment_name, attachment_content, mime_type = sent.attachments[0]
        self.assertEqual(attachment_name, "OSCA_Progress_Report.pdf")
        self.assertEqual(mime_type, "application/pdf")

    def test_weekly_progress_summary_streak_subject(self):
        """Test weekly_progress_summary streak subject line when XP is zero."""
        payload = {
            "template_id": "weekly_progress_summary",
            "recipients": [self.user.email],
            "data": {
                "username": self.user.username,
                "xp_earned": 0,
                "current_streak": 7,
                "lessons_completed": 0,
                "rank": 10,
                "start_date": "2026-07-01",
                "end_date": "2026-07-07",
            },
        }

        send_bulk_email(payload)

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertIn("7-day streak", sent.subject)

    def test_badge_earned_email(self):
        """Test badge_earned_email template rendering and dispatch."""
        payload = {
            "template_id": "badge_earned_email",
            "recipients": [self.user.email],
            "data": {
                "badge_name": "Python Master",
                "username": self.user.username,
            },
        }

        send_bulk_email(payload)

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertIn("You Earned a New Badge!", sent.subject)
        self.assertIn("Python Master", sent.body)

    def test_comment_posted_email(self):
        """Test comment_posted_email template rendering and dispatch."""
        payload = {
            "template_id": "comment_posted_email",
            "recipients": [self.user.email],
            "data": {
                "reviewer_name": "ReviewerAlice",
                "username": self.user.username,
                "feedback": "Great job on the clean code architecture!",
            },
        }

        send_bulk_email(payload)

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertIn("New Peer Review on Your Submission", sent.subject)
        self.assertIn("ReviewerAlice", sent.body)
        self.assertIn("Great job on the clean code architecture!", sent.body)

    def test_notification_digest_email(self):
        """Test notification_digest template rendering and dispatch."""
        payload = {
            "template_id": "notification_digest",
            "recipients": [self.user.email],
            "data": {
                "digest_frequency": "weekly",
                "total_count": 3,
                "grouped_notifications": {},
            },
        }

        send_bulk_email(payload)

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertIn("Weekly Notification Digest", sent.subject)

    def test_send_notification_digests_triggers_bulk_email(self):
        """Test send_notification_digests integration calling send_bulk_email."""
        from django.utils import timezone

        # Enable notification preference for user
        pref, _ = NotificationPreference.objects.get_or_create(user=self.user)
        pref.digest_frequency = "daily"
        pref.digest_time = timezone.now().time()
        pref.save()

        # Create an unread notification
        Notification.objects.create(
            recipient=self.user,
            notif_type="badge",
            title="Badge Awarded",
            message="Unlocked Python Badge",
            is_read=False,
        )

        send_notification_digests()

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertIn("Daily Notification Digest", sent.subject)
