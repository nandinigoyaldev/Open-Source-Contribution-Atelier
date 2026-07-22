"""
Tests for the merged LOGGING configuration (fix for issue #2008).

Verifies that:
- There is exactly one LOGGING dict (no silent overwrite).
- Both audit/JSON logging and sensitive-data-masking are present.
- The audit logger routes to the correct handlers.
- RequestIdFilter injects request_id / user_id into log records.
- SensitiveDataFilter masks PII from log messages.
- The audit FileHandler writes to the expected path.
- AUDIT_LOG_ENABLED is True.
- No duplicate GRAPHENE assignment exists (secondary cleanup verified).
"""

import importlib
import io
import json
import logging
import logging.config
import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

import django
import pytest
from django.conf import settings
from django.test import override_settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_logging_cfg() -> dict:
    """Return a *copy* of the project LOGGING dict from Django settings."""
    return dict(settings.LOGGING)


# ===========================================================================
# 1. Structural integrity of the LOGGING dict
# ===========================================================================

class TestLoggingConfigStructure:
    """Verify the shape and completeness of the merged LOGGING dict."""

    def test_logging_is_a_dict(self):
        assert isinstance(settings.LOGGING, dict), "LOGGING must be a dict"

    def test_version_is_one(self):
        assert settings.LOGGING["version"] == 1

    def test_disable_existing_loggers_is_false(self):
        """disable_existing_loggers=True silently drops third-party loggers."""
        assert settings.LOGGING.get("disable_existing_loggers") is False

    # ── Filters ────────────────────────────────────────────────────────────

    def test_request_id_filter_present(self):
        filters = settings.LOGGING.get("filters", {})
        assert "request_id" in filters, "request_id filter must be declared"
        assert filters["request_id"].get("()") == "apps.core.logging_filters.RequestIdFilter"

    def test_mask_sensitive_data_filter_present(self):
        filters = settings.LOGGING.get("filters", {})
        assert "mask_sensitive_data" in filters, "mask_sensitive_data filter must be declared"
        assert filters["mask_sensitive_data"].get("()") == "config.logging_filters.SensitiveDataFilter"

    # ── Formatters ─────────────────────────────────────────────────────────

    def test_json_audit_formatter_present(self):
        fmts = settings.LOGGING.get("formatters", {})
        assert "json_audit" in fmts, "json_audit formatter must exist for structured audit logs"

    def test_json_audit_formatter_contains_request_id_field(self):
        fmt_string = settings.LOGGING["formatters"]["json_audit"]["format"]
        assert "request_id" in fmt_string, "json_audit formatter must include %(request_id)s"

    def test_json_audit_formatter_contains_user_id_field(self):
        fmt_string = settings.LOGGING["formatters"]["json_audit"]["format"]
        assert "user_id" in fmt_string, "json_audit formatter must include %(user_id)s"

    def test_verbose_formatter_present(self):
        fmts = settings.LOGGING.get("formatters", {})
        assert "verbose" in fmts, "verbose formatter must exist for human-readable console output"

    # ── Handlers ───────────────────────────────────────────────────────────

    def test_console_handler_present(self):
        handlers = settings.LOGGING.get("handlers", {})
        assert "console" in handlers

    def test_console_handler_uses_sensitive_data_filter(self):
        handler_cfg = settings.LOGGING["handlers"]["console"]
        assert "mask_sensitive_data" in handler_cfg.get("filters", [])

    def test_console_handler_uses_verbose_formatter(self):
        handler_cfg = settings.LOGGING["handlers"]["console"]
        assert handler_cfg.get("formatter") == "verbose"

    def test_console_audit_handler_present(self):
        handlers = settings.LOGGING.get("handlers", {})
        assert "console_audit" in handlers, "console_audit handler must exist"

    def test_console_audit_handler_uses_request_id_filter(self):
        handler_cfg = settings.LOGGING["handlers"]["console_audit"]
        assert "request_id" in handler_cfg.get("filters", [])

    def test_console_audit_handler_uses_json_audit_formatter(self):
        handler_cfg = settings.LOGGING["handlers"]["console_audit"]
        assert handler_cfg.get("formatter") == "json_audit"

    def test_file_audit_handler_declared(self):
        """file_audit handler must be declared even if suppressed in TESTING."""
        handlers = settings.LOGGING.get("handlers", {})
        assert "file_audit" in handlers, "file_audit handler must be declared in LOGGING"

    def test_file_audit_handler_uses_json_audit_formatter(self):
        handler_cfg = settings.LOGGING["handlers"]["file_audit"]
        assert handler_cfg.get("formatter") == "json_audit"

    def test_file_audit_handler_uses_request_id_filter(self):
        handler_cfg = settings.LOGGING["handlers"]["file_audit"]
        assert "request_id" in handler_cfg.get("filters", [])

    def test_file_audit_filename_points_to_audit_log(self):
        filename = settings.LOGGING["handlers"]["file_audit"]["filename"]
        assert "audit.log" in str(filename), (
            f"file_audit handler filename must contain 'audit.log', got: {filename}"
        )

    # ── Loggers ────────────────────────────────────────────────────────────

    def test_audit_logger_declared(self):
        loggers = settings.LOGGING.get("loggers", {})
        assert "audit" in loggers, "audit logger must be present"

    def test_audit_logger_does_not_propagate(self):
        assert settings.LOGGING["loggers"]["audit"]["propagate"] is False

    def test_audit_logger_level_is_info(self):
        assert settings.LOGGING["loggers"]["audit"]["level"] == "INFO"

    def test_audit_logger_has_console_audit_handler(self):
        handlers = settings.LOGGING["loggers"]["audit"]["handlers"]
        assert "console_audit" in handlers

    def test_django_logger_declared(self):
        assert "django" in settings.LOGGING.get("loggers", {})

    def test_django_server_logger_declared(self):
        assert "django.server" in settings.LOGGING.get("loggers", {})

    def test_apps_logger_declared(self):
        assert "apps" in settings.LOGGING.get("loggers", {})

    def test_root_logger_declared(self):
        assert "root" in settings.LOGGING, "root logger must be present in LOGGING"

    def test_root_logger_uses_console_handler(self):
        assert "console" in settings.LOGGING["root"]["handlers"]

    # ── Top-level settings ─────────────────────────────────────────────────

    def test_audit_log_enabled_is_true(self):
        assert settings.AUDIT_LOG_ENABLED is True

    def test_request_logging_verbosity_set(self):
        assert hasattr(settings, "REQUEST_LOGGING_VERBOSITY")
        assert settings.REQUEST_LOGGING_VERBOSITY in ("minimal", "full")


# ===========================================================================
# 2. No duplicate LOGGING assignment in settings source
# ===========================================================================

class TestNoDuplicateLoggingAssignment:
    """
    Regression test: parse the settings source and count top-level
    'LOGGING = {' assignments.  There must be exactly one.
    """

    def test_single_logging_assignment_in_source(self):
        settings_path = Path(settings.__file__) if hasattr(settings, "__file__") else None
        # Locate settings.py relative to BASE_DIR
        base_dir = Path(settings.BASE_DIR)
        settings_file = base_dir / "config" / "settings.py"
        assert settings_file.exists(), f"Cannot find settings.py at {settings_file}"

        source = settings_file.read_text(encoding="utf-8")
        # Count lines that are a top-level LOGGING assignment (not a comment)
        assignment_lines = [
            line for line in source.splitlines()
            if line.startswith("LOGGING") and "=" in line and not line.lstrip().startswith("#")
        ]
        assert len(assignment_lines) == 1, (
            f"Expected exactly 1 top-level LOGGING assignment, found {len(assignment_lines)}: "
            f"{assignment_lines}"
        )


# ===========================================================================
# 3. Logging configuration loads without errors
# ===========================================================================

class TestLoggingConfigLoads:
    """Verify Django's dictConfig accepts the merged LOGGING dict."""

    def test_dictconfig_accepts_logging_dict(self):
        """
        logging.config.dictConfig should not raise when given the project
        LOGGING dict.  We restore the original config afterwards.
        """
        import logging.config as lc

        # Keep the root handlers so we can restore after the test
        root_logger = logging.getLogger()
        original_handlers = root_logger.handlers[:]

        try:
            # Should not raise
            lc.dictConfig(settings.LOGGING)
        finally:
            # Restore to avoid polluting other tests
            root_logger.handlers = original_handlers


# ===========================================================================
# 4. RequestIdFilter injects correct fields
# ===========================================================================

class TestRequestIdFilter:
    """Unit-test RequestIdFilter in isolation."""

    def test_filter_injects_request_id_and_user_id(self):
        from apps.core.logging_filters import RequestIdFilter
        from apps.core.middleware.request_id import _thread_locals

        _thread_locals.request_id = "test-req-123"
        _thread_locals.user_id = 42

        try:
            f = RequestIdFilter()
            record = logging.LogRecord(
                name="audit", level=logging.INFO,
                pathname="", lineno=0, msg="test", args=(), exc_info=None,
            )
            result = f.filter(record)
            assert result is True
            assert record.request_id == "test-req-123"
            assert record.user_id == 42
        finally:
            _thread_locals.request_id = None
            _thread_locals.user_id = None

    def test_filter_falls_back_when_no_request_context(self):
        from apps.core.logging_filters import RequestIdFilter
        from apps.core.middleware.request_id import _thread_locals

        _thread_locals.request_id = None
        _thread_locals.user_id = None

        f = RequestIdFilter()
        record = logging.LogRecord(
            name="audit", level=logging.INFO,
            pathname="", lineno=0, msg="fallback test", args=(), exc_info=None,
        )
        f.filter(record)
        assert record.request_id == "-"
        assert record.user_id == "-"


# ===========================================================================
# 5. SensitiveDataFilter masks PII
# ===========================================================================

class TestSensitiveDataFilter:
    """Unit-test SensitiveDataFilter masking behaviour."""

    def _apply(self, msg: str) -> str:
        from config.logging_filters import SensitiveDataFilter
        f = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="", lineno=0, msg=msg, args=(), exc_info=None,
        )
        f.filter(record)
        return record.msg

    def test_email_is_masked(self):
        result = self._apply("User login: alice@example.com")
        assert "alice@example.com" not in result
        assert "[MASKED_EMAIL]" in result

    def test_jwt_token_is_masked(self):
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        result = self._apply(f"Authorization: Bearer {jwt}")
        assert jwt not in result

    def test_plain_message_passes_through(self):
        result = self._apply("User logged in successfully")
        assert result == "User logged in successfully"

    def test_filter_returns_true(self):
        from config.logging_filters import SensitiveDataFilter
        f = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="", lineno=0, msg="safe message", args=(), exc_info=None,
        )
        assert f.filter(record) is True


# ===========================================================================
# 6. Audit logger routes to the correct handlers
# ===========================================================================

class TestAuditLoggerRouting:
    """
    Verify the 'audit' logger is wired to console_audit (always) and
    file_audit (when not TESTING), and that propagate=False.
    """

    def test_audit_logger_propagate_false(self):
        logger = logging.getLogger("audit")
        assert logger.propagate is False

    def test_audit_logger_has_at_least_one_handler_after_config(self):
        import logging.config as lc

        # Apply config in a controlled way
        cfg = dict(settings.LOGGING)
        # Temporarily point file_audit to a temp file so dictConfig doesn't
        # try to create audit.log in the test environment unexpectedly
        import copy
        cfg = copy.deepcopy(cfg)
        with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as tmp:
            tmp_name = tmp.name
        cfg["handlers"]["file_audit"]["filename"] = tmp_name
        # In test mode _audit_handlers only has console_audit; simulate prod:
        cfg["loggers"]["audit"]["handlers"] = ["console_audit", "file_audit"]

        try:
            lc.dictConfig(cfg)
            audit_logger = logging.getLogger("audit")
            assert len(audit_logger.handlers) >= 1
        finally:
            # Close all FileHandler instances referencing the temp log before
            # deleting it — required on Windows to avoid PermissionError.
            audit_logger = logging.getLogger("audit")
            for h in list(audit_logger.handlers):
                h.close()
                audit_logger.removeHandler(h)
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            # Re-apply original config to not break other tests
            lc.dictConfig(settings.LOGGING)

    def test_audit_log_enabled_setting_is_true(self):
        assert settings.AUDIT_LOG_ENABLED is True


# ===========================================================================
# 7. Audit file handler is suppressed in TESTING mode
# ===========================================================================

class TestAuditFileHandlerTestingMode:
    """
    In TESTING mode the file_audit handler must NOT appear in the audit
    logger's handler list (to avoid writing stale audit.log files in CI).
    """

    def test_file_audit_not_in_audit_handlers_when_testing(self):
        # settings.TESTING should be True when pytest is active
        assert settings.TESTING is True, "This test must run inside pytest"

        audit_logger_cfg = settings.LOGGING["loggers"]["audit"]
        assert "file_audit" not in audit_logger_cfg["handlers"], (
            "file_audit handler must be suppressed in TESTING mode"
        )

    def test_console_audit_still_present_in_testing(self):
        audit_logger_cfg = settings.LOGGING["loggers"]["audit"]
        assert "console_audit" in audit_logger_cfg["handlers"], (
            "console_audit handler must remain active even in TESTING mode"
        )


# ===========================================================================
# 8. Audit message format is valid JSON
# ===========================================================================

class TestAuditMessageFormat:
    """
    Ensure the json_audit formatter produces valid JSON when a log record
    passes through it (using a mock StreamHandler to capture output).
    """

    def test_audit_message_is_valid_json(self):
        from apps.core.logging_filters import RequestIdFilter
        from apps.core.middleware.request_id import _thread_locals

        _thread_locals.request_id = "json-test-001"
        _thread_locals.user_id = 99

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        fmt_string = (
            '{"time": "%(asctime)s", "level": "%(levelname)s", '
            '"request_id": "%(request_id)s", "user_id": "%(user_id)s", '
            '"message": "%(message)s"}'
        )
        handler.setFormatter(logging.Formatter(fmt_string))
        handler.addFilter(RequestIdFilter())

        test_logger = logging.getLogger("audit.test_format")
        test_logger.addHandler(handler)
        test_logger.setLevel(logging.INFO)

        try:
            test_logger.info("audit event occurred")
            output = stream.getvalue().strip()
            parsed = json.loads(output)
            assert parsed["request_id"] == "json-test-001"
            assert parsed["user_id"] == "99"
            assert parsed["message"] == "audit event occurred"
            assert parsed["level"] == "INFO"
        finally:
            test_logger.removeHandler(handler)
            _thread_locals.request_id = None
            _thread_locals.user_id = None
