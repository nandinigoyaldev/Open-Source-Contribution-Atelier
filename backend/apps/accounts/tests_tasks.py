from unittest.mock import patch

from django.conf import settings
from django.test import TestCase

from .tasks import send_otp_email_task, send_password_reset_email_task


class CeleryEmailTasksTests(TestCase):
    @patch("apps.accounts.tasks.send_mail")
    def test_send_password_reset_email_task(self, mock_send_mail):
        """Verify the password reset email task formats correctly and calls send_mail."""
        user_email = "test@example.com"
        user_username = "testuser"
        reset_url = "http://localhost:5173/reset-password?token=abc"
        timeout = 15

        send_password_reset_email_task(user_email, user_username, reset_url, timeout)

        mock_send_mail.assert_called_once()
        kwargs = mock_send_mail.call_args.kwargs
        self.assertEqual(kwargs["subject"], "Password Reset Request")
        self.assertEqual(kwargs["recipient_list"], [user_email])
        self.assertIn(reset_url, kwargs["message"])
        self.assertIn(user_username, kwargs["message"])
        self.assertEqual(
            kwargs["from_email"],
            getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@atelier.dev"),
        )
        self.assertFalse(kwargs["fail_silently"])

    @patch("apps.accounts.tasks.send_mail")
    def test_send_otp_email_task(self, mock_send_mail):
        """Verify the OTP verification email task formats correctly and calls send_mail."""
        user_email = "otp@example.com"
        user_username = "otpuser"
        otp_token = "123456"

        send_otp_email_task(user_email, user_username, otp_token)

        mock_send_mail.assert_called_once()
        kwargs = mock_send_mail.call_args.kwargs
        self.assertEqual(kwargs["subject"], "Your Verification Code")
        self.assertEqual(kwargs["recipient_list"], [user_email])
        self.assertIn(otp_token, kwargs["message"])
        self.assertIn(user_username, kwargs["message"])
        self.assertEqual(
            kwargs["from_email"],
            getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@atelier.dev"),
        )
        self.assertFalse(kwargs["fail_silently"])
