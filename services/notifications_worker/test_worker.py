import unittest
import io
import sys
import logging

from worker import send_bulk_email, logger


class TestNotificationsWorker(unittest.TestCase):
    def setUp(self):
        # Capture logs
        self.log_capture = io.StringIO()
        self.handler = logging.StreamHandler(self.log_capture)
        logger.addHandler(self.handler)
        logger.setLevel(logging.INFO)

    def tearDown(self):
        logger.removeHandler(self.handler)

    def test_send_bulk_email_success(self):
        payload = {
            "template_id": "badge_earned_email",
            "recipients": ["test1@example.com", "test2@example.com"],
            "data": {"badge_name": "First PR"},
        }

        result = send_bulk_email(payload)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["recipients_count"], 2)

        logs = self.log_capture.getvalue()
        self.assertIn("Email successfully dispatched to test1@example.com", logs)
        self.assertIn("Email successfully dispatched to test2@example.com", logs)

    def test_send_bulk_email_no_recipients(self):
        payload = {"template_id": "badge_earned_email", "recipients": [], "data": {}}

        result = send_bulk_email(payload)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["recipients_count"], 0)

        logs = self.log_capture.getvalue()
        self.assertNotIn("Email successfully dispatched", logs)

    def test_send_bulk_email_missing_fields(self):
        # Empty payload
        result = send_bulk_email({})
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["recipients_count"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
