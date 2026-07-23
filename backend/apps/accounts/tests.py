from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import UserProfile
from apps.accounts.tasks import send_notification_email_task

User = get_user_model()


class NotificationTaskTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="testpassword123",
        )
        # Create user profile explicitly
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)

    @patch("apps.accounts.tasks.send_mail")
    def test_notification_sent_when_dnd_is_disabled(self, mock_send_mail):
        """
        Verify that notification emails are sent when Do Not Disturb is False.
        """
        self.profile.do_not_disturb = False
        self.profile.save()

        result = send_notification_email_task(
            user_email=self.user.email,
            subject="Welcome to Atelier",
            message_body="Thank you for contributing!",
        )

        self.assertEqual(result, f"Email sent successfully to {self.user.email}")
        mock_send_mail.assert_called_once_with(
            subject="Welcome to Atelier",
            message="Thank you for contributing!",
            from_email="noreply@atelier.dev",
            recipient_list=["testuser@example.com"],
            fail_silently=False,
        )

    @patch("apps.accounts.tasks.send_mail")
    def test_notification_skipped_when_dnd_is_enabled(self, mock_send_mail):
        """
        Verify that notification emails are completely suppressed when DND is True.
        """
        self.profile.do_not_disturb = True
        self.profile.save()

        result = send_notification_email_task(
            user_email=self.user.email,
            subject="New Peer Review Assignment",
            message_body="Please review this code submission.",
        )

        self.assertEqual(result, "Email skipped: User has 'Do Not Disturb' enabled.")
        mock_send_mail.assert_not_called()

    @patch("apps.accounts.tasks.send_mail")
    def test_notification_sent_when_user_profile_missing(self, mock_send_mail):
        """
        Verify fallback behavior: If a user lacks a UserProfile, send email by default.
        """
        user_without_profile = User.objects.create_user(
            username="noprofileuser",
            email="noprofile@example.com",
            password="testpassword123",
        )
        # Ensure profile does not exist
        UserProfile.objects.filter(user=user_without_profile).delete()

        result = send_notification_email_task(
            user_email=user_without_profile.email,
            subject="System Update",
            message_body="Important system maintenance scheduled.",
        )

        self.assertEqual(
            result, f"Email sent successfully to {user_without_profile.email}"
        )
        mock_send_mail.assert_called_once()
