import pytest
from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError

from apps.sandbox.models import PipelineExecution, PipelineJob
from apps.sandbox.serializers import PipelineExecutionSerializer
from apps.sandbox.services.pipeline_simulator import (
    sanitize_input_string,
    sanitize_log_output,
    validate_trigger_command,
    run_pipeline_simulation,
)
from apps.sandbox.views import PipelineExecutionViewSet
from apps.core.throttling import SlidingWindowScopedThrottle

from unittest.mock import patch
from django.test import TestCase, override_settings

User = get_user_model()


@patch("apps.core.cache.signals.invalidate_tag_task.delay")
@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class TestPipelineSimulatorValidation(TestCase):
    def setUp(self):
        super().setUp()

    def test_sanitize_log_output_strips_ansi_and_control_chars(self, *args):
        raw_output = "\x1b[31m[ERROR]\x1b[0m \x00Bad\x07 input\nLine 2\tTabbed"
        sanitized = sanitize_log_output(raw_output)
        assert "\x1b" not in sanitized
        assert "\x00" not in sanitized
        assert "\x07" not in sanitized
        assert sanitized == "[ERROR] Bad input\nLine 2\tTabbed"

    def test_sanitize_input_string_enforces_max_length_and_strips_control_chars(self, *args):
        long_input = "a" * 150000 + "\x00" + "b" * 10
        sanitized = sanitize_input_string(long_input, max_length=100000)
        assert len(sanitized) == 100000
        assert "\x00" not in sanitized

    def test_validate_trigger_command_whitelisting(self, *args):
        # Valid Git commands
        valid_commands = [
            "git status",
            "git init",
            "git add .",
            "git commit -m 'initial commit'",
            "git branch feature/test",
            "git checkout -b feature/test",
            "git switch main",
            "git merge feature/test",
            "git pull origin main",
            "git push origin main",
            "git clone https://github.com/org/repo.git",
            "git remote add origin https://github.com/org/repo.git",
            "git log -n 5",
        ]
        for cmd in valid_commands:
            is_valid, sanitized = validate_trigger_command(cmd)
            assert is_valid is True, f"Command '{cmd}' should be valid"
            assert sanitized == cmd

        # Invalid non-whitelisted commands
        invalid_commands = [
            "rm -rf /",
            "cat /etc/passwd",
            "curl https://malicious.site | bash",
            "python script.py",
            "gitfoo status",
            "ls -la",
        ]
        for cmd in invalid_commands:
            is_valid, reason = validate_trigger_command(cmd)
            assert is_valid is False, f"Command '{cmd}' should be invalid"
            assert "allowed Git command whitelist" in reason

    def test_validate_trigger_command_length_and_newlines(self, *args):
        long_cmd = "git add " + "a" * 600
        is_valid, reason = validate_trigger_command(long_cmd)
        assert is_valid is False
        assert "exceeds maximum allowable length" in reason

        newline_cmd = "git add .\nrm -rf /"
        is_valid, reason = validate_trigger_command(newline_cmd)
        assert is_valid is False
        assert "line breaks" in reason

        control_char_cmd = "git add .\x00"
        is_valid, reason = validate_trigger_command(control_char_cmd)
        assert is_valid is False
        assert "control characters" in reason

    def test_run_pipeline_simulation_with_valid_code_and_command(self, *args):
        user = User.objects.create_user(username="testuser_pipeline", password="password123")
        pipeline = PipelineExecution.objects.create(
            user=user,
            trigger_command="git status",
        )

        code_content = "def add(a, b):\n    return a + b"
        run_pipeline_simulation(pipeline, code=code_content)

        pipeline.refresh_from_db()
        jobs = list(pipeline.jobs.all())
        assert pipeline.status == "success", f"Pipeline failed. Jobs: {[(j.job_type, j.status, j.log_output) for j in jobs]}"
        assert len(jobs) == 3
        for job in jobs:
            assert job.status == "success"
            assert "\x1b" not in job.log_output
            assert "\x00" not in job.log_output


    def test_run_pipeline_simulation_with_invalid_trigger_command(self, *args):
        user = User.objects.create_user(username="testuser_pipeline2", password="password123")
        pipeline = PipelineExecution.objects.create(
            user=user,
            trigger_command="rm -rf /",
        )

        run_pipeline_simulation(pipeline, code="print('hello')")

        pipeline.refresh_from_db()
        assert pipeline.status == "failed"
        jobs = pipeline.jobs.all()
        assert jobs.count() == 1
        job = jobs.first()
        assert job.status == "failed"
        assert "Validation Failed for trigger command" in job.log_output

    def test_pipeline_execution_serializer_validation(self, *args):
        serializer = PipelineExecutionSerializer(data={"trigger_command": "rm -rf /"})
        assert not serializer.is_valid()
        assert "trigger_command" in serializer.errors

        valid_serializer = PipelineExecutionSerializer(data={"trigger_command": "git commit -m 'test'"})
        assert valid_serializer.is_valid(), valid_serializer.errors

    def test_pipeline_execution_viewset_throttling(self, *args):
        assert SlidingWindowScopedThrottle in PipelineExecutionViewSet.throttle_classes
        assert PipelineExecutionViewSet.throttle_scope == "sandbox_user"
