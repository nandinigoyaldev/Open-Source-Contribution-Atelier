import logging

from django.test import TestCase

from apps.sandbox.telemetry import (
    TRUNCATION_COUNTER_NAME,
    categorize_command,
    get_all_truncation_counts,
    get_truncation_count,
    record_output_truncation,
    reset_telemetry,
    truncate_sandbox_output,
)
from apps.sandbox.verifier import SandboxVerifier


class SandboxOutputTruncationTelemetryTests(TestCase):
    def setUp(self):
        super().setUp()
        reset_telemetry()

    def tearDown(self):
        reset_telemetry()
        super().tearDown()

    def test_stdout_truncation_emits_telemetry(self):
        content = "A" * 250
        limit = 100
        truncated, was_truncated = truncate_sandbox_output(
            content,
            stream="stdout",
            command='git commit -m "feat: initial commit"',
            limit=limit,
        )

        self.assertTrue(was_truncated)
        self.assertEqual(len(truncated), limit)
        self.assertEqual(get_truncation_count("stdout", "commit", limit), 1)
        # stderr must not be affected
        self.assertEqual(get_truncation_count("stderr", "commit", limit), 0)

    def test_stderr_truncation_emits_telemetry(self):
        content = "Error: fatal error details occurred here " * 5
        limit = 40
        truncated, was_truncated = truncate_sandbox_output(
            content,
            stream="stderr",
            command="git status",
            limit=limit,
        )

        self.assertTrue(was_truncated)
        self.assertEqual(len(truncated), limit)
        self.assertEqual(get_truncation_count("stderr", "status", limit), 1)
        # stdout must not be affected
        self.assertEqual(get_truncation_count("stdout", "status", limit), 0)

    def test_within_limit_does_not_emit_telemetry(self):
        content = "Short output within limits."
        limit = 500
        truncated, was_truncated = truncate_sandbox_output(
            content,
            stream="stdout",
            command="git status",
            limit=limit,
        )

        self.assertFalse(was_truncated)
        self.assertEqual(truncated, content)
        self.assertEqual(len(get_all_truncation_counts()), 0)

    def test_metrics_distinguish_stdout_and_stderr(self):
        long_text = "X" * 300
        limit = 50

        truncate_sandbox_output(
            long_text,
            stream="stdout",
            command="git checkout -b feature-test",
            limit=limit,
        )
        truncate_sandbox_output(
            long_text,
            stream="stderr",
            command="git checkout -b feature-test",
            limit=limit,
        )

        self.assertEqual(get_truncation_count("stdout", "checkout", limit), 1)
        self.assertEqual(get_truncation_count("stderr", "checkout", limit), 1)

    def test_command_categorization_is_privacy_safe(self):
        # Sensitive arguments, credentials, and messages must never be in category
        self.assertEqual(
            categorize_command('git commit -m "secret_token_ghp_1234567890abcdef"'),
            "commit",
        )
        self.assertEqual(
            categorize_command(
                "git push https://user:secretpass@github.com/repo.git main"
            ),
            "push",
        )
        self.assertEqual(
            categorize_command("git checkout -b secret-branch-name"),
            "checkout",
        )
        self.assertEqual(
            categorize_command("git switch main"),
            "switch",
        )
        self.assertEqual(
            categorize_command("git merge feature/private-work"),
            "merge",
        )
        self.assertEqual(
            categorize_command("git rebase origin/main"),
            "rebase",
        )
        self.assertEqual(
            categorize_command("git status --short"),
            "status",
        )
        self.assertEqual(
            categorize_command("python -c 'import os; print(os.environ)'"),
            "python",
        )
        self.assertEqual(
            categorize_command("python3 run_script.py --api-key=SECRET"),
            "python",
        )
        self.assertEqual(
            categorize_command(""),
            "unknown",
        )
        self.assertEqual(
            categorize_command(None),
            "unknown",
        )

    def test_output_content_and_secrets_are_never_logged(self):
        secret_content = (
            "SECRET_API_KEY=AKIAIOSFODNN7EXAMPLE Bearer super_secret_token_12345"
        )
        limit = 20

        # Capture logs emitted under apps.sandbox.telemetry
        with self.assertLogs("apps.sandbox.telemetry", level="INFO") as captured_logs:
            truncate_sandbox_output(
                secret_content,
                stream="stdout",
                command='git commit -m "commit with SECRET_API_KEY"',
                limit=limit,
            )

        log_output = "\n".join(captured_logs.output)

        # Output content, secrets, and commit message must NOT appear in logs
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", log_output)
        self.assertNotIn("super_secret_token_12345", log_output)
        self.assertNotIn("Bearer", log_output)
        self.assertNotIn("SECRET_API_KEY", log_output)
        self.assertNotIn("commit with", log_output)

        # Only privacy-safe metadata should appear
        self.assertIn("stream=stdout", log_output)
        self.assertIn("command_category=commit", log_output)
        self.assertIn(f"limit={limit}", log_output)

    def test_configured_limits_distinguished_in_metrics(self):
        content = "Z" * 500

        truncate_sandbox_output(
            content,
            stream="stdout",
            command="git log -n 5",
            limit=100,
        )
        truncate_sandbox_output(
            content,
            stream="stdout",
            command="git log -n 5",
            limit=200,
        )

        self.assertEqual(get_truncation_count("stdout", "log", 100), 1)
        self.assertEqual(get_truncation_count("stdout", "log", 200), 1)
        self.assertEqual(get_truncation_count("stdout", "log", 300), 0)

    def test_existing_verifier_behavior_is_unchanged(self):
        raw_log = [
            {
                "timestamp": 1.0,
                "command": "git checkout -b feature-ui",
                "stdout": "Switched to a new branch 'feature-ui'\n" + ("x" * 200),
                "stderr": "",
            },
            {
                "timestamp": 2.0,
                "command": "git add .",
                "stdout": "",
                "stderr": "",
            },
            {
                "timestamp": 3.0,
                "command": 'git commit -m "add navigation UI"',
                "stdout": "[feature-ui 1234567] add navigation UI\n" + ("y" * 300),
                "stderr": "warning: LF will be replaced by CRLF\n" + ("z" * 200),
            },
        ]
        expected = [
            "git checkout -b feature-ui",
            "git add .",
            'git commit -m "add navigation UI"',
        ]

        # Verify evaluation with truncation enabled
        res_with_truncation = SandboxVerifier.evaluate_session(
            raw_log, expected, max_output_length=50
        )

        # Verify evaluation without truncation
        res_without_truncation = SandboxVerifier.evaluate_session(raw_log, expected)

        # Scores, steps, percentage, and passed status must match exactly
        self.assertEqual(
            res_with_truncation["passed"], res_without_truncation["passed"]
        )
        self.assertEqual(
            res_with_truncation["total_score"], res_without_truncation["total_score"]
        )
        self.assertEqual(
            res_with_truncation["max_score"], res_without_truncation["max_score"]
        )
        self.assertEqual(
            res_with_truncation["percentage"], res_without_truncation["percentage"]
        )
        self.assertEqual(
            len(res_with_truncation["steps"]), len(res_without_truncation["steps"])
        )

        # Telemetry should have captured the truncation events
        self.assertEqual(get_truncation_count("stdout", "checkout", 50), 1)
        self.assertEqual(get_truncation_count("stdout", "commit", 50), 1)
        self.assertEqual(get_truncation_count("stderr", "commit", 50), 1)

    def test_sandbox_verifier_convenience_methods(self):
        output = "Large output string " * 20
        limit = 30

        truncated = SandboxVerifier.truncate_output(
            output,
            stream="stdout",
            command="git diff",
            limit=limit,
        )

        self.assertEqual(len(truncated), limit)
        self.assertEqual(get_truncation_count("stdout", "diff", limit), 1)

        SandboxVerifier.record_truncation("stderr", "python", 1024)
        self.assertEqual(get_truncation_count("stderr", "python", 1024), 1)
