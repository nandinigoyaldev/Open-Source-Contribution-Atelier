from django.test import SimpleTestCase

from apps.cache.audit_logger import AuditLogger

REDACTED = "***REDACTED***"


class AuditLoggerSanitizeTests(SimpleTestCase):
    def test_exact_sensitive_names_are_redacted(self):
        data = {
            "password": "p",
            "token": "t",
            "secret": "s",
            "key": "k",
            "authorization": "a",
            "name": "n",
        }
        self.assertEqual(
            AuditLogger._sanitize_data(data),
            {
                "password": REDACTED,
                "token": REDACTED,
                "secret": REDACTED,
                "key": REDACTED,
                "authorization": REDACTED,
                "name": "n",
            },
        )

    def test_names_that_contain_a_sensitive_word_are_redacted(self):
        data = {
            "new_password": "x",
            "old_password": "x",
            "confirm_password": "x",
            "access_token": "x",
            "refresh_token": "x",
            "Authorization": "Bearer x",
            "client_secret": "x",
            "api_key": "x",
            "ApiKey": "x",
            "username": "kept",
        }
        out = AuditLogger._sanitize_data(data)
        self.assertEqual([k for k, v in out.items() if v != REDACTED], ["username"])

    def test_nested_objects_and_lists_are_sanitized(self):
        data = {
            "user": {"name": "a", "password": "p"},
            "users": [{"email": "e", "password": "p"}, {"token": "t"}],
            "matrix": [[{"secret": "s"}]],
        }
        self.assertEqual(
            AuditLogger._sanitize_data(data),
            {
                "user": {"name": "a", "password": REDACTED},
                "users": [{"email": "e", "password": REDACTED}, {"token": REDACTED}],
                "matrix": [[{"secret": REDACTED}]],
            },
        )

    def test_a_list_body_no_longer_crashes(self):
        self.assertEqual(
            AuditLogger._sanitize_data([1, "a", {"password": "p"}]),
            [1, "a", {"password": REDACTED}],
        )

    def test_other_json_values_pass_through(self):
        for value in ("text", 5, 1.5, True, None):
            self.assertEqual(AuditLogger._sanitize_data(value), value)

    def test_input_is_not_modified(self):
        data = {"password": "p", "nested": [{"token": "t"}]}
        AuditLogger._sanitize_data(data)
        self.assertEqual(data, {"password": "p", "nested": [{"token": "t"}]})

    def test_log_accepts_a_list_request_body(self):
        with self.assertLogs("audit", level="INFO") as logs:
            AuditLogger.log(
                user_id=None,
                action="POST",
                resource="/api/x/",
                resource_id=None,
                method="POST",
                ip_address="127.0.0.1",
                status_code=400,
                request_data=[{"password": "hunter2"}],
            )
        self.assertNotIn("hunter2", logs.output[0])
        self.assertIn(REDACTED, logs.output[0])
