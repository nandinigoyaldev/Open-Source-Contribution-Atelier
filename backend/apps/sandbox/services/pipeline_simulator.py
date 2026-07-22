"""
CI/CD Pipeline Simulation Service with Input Sanitization, Command Whitelisting, and Log Output Protection.
"""

import random
import re
from datetime import datetime, timezone

MAX_CODE_LENGTH = 100000
MAX_COMMAND_LENGTH = 512

# ANSI escape sequence pattern
ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

# Non-printable control character pattern (preserving \n, \r, \t)
CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")


def sanitize_log_output(text: str) -> str:
    """
    Sanitize console/log output strings to prevent ANSI escape injection
    and control character injection in log displays.
    """
    if not text:
        return ""
    # Strip ANSI escape sequences
    sanitized = ANSI_ESCAPE_RE.sub("", text)
    # Strip non-printable control characters except \n, \r, \t
    sanitized = CONTROL_CHAR_RE.sub("", sanitized)
    return sanitized


def sanitize_input_string(text: str, max_length: int = MAX_CODE_LENGTH) -> str:
    """
    Sanitize and enforce size limits on input strings.
    """
    if not text:
        return ""
    # Enforce maximum length
    truncated = text[:max_length]
    # Remove null bytes and dangerous control characters
    return CONTROL_CHAR_RE.sub("", truncated)


def validate_trigger_command(command: str) -> tuple[bool, str]:
    """
    Validate a pipeline trigger command against length limits, character-set
    restrictions, and the whitelisted Git command allowlist.
    """
    from apps.sandbox.services import ALLOWED_PREFIXES

    if not command or not command.strip():
        return True, ""

    cmd = command.strip()

    if len(cmd) > MAX_COMMAND_LENGTH:
        return False, f"Command exceeds maximum allowable length of {MAX_COMMAND_LENGTH} characters."

    if "\n" in cmd or "\r" in cmd:
        return False, "Command must not contain line breaks or newlines."

    if CONTROL_CHAR_RE.search(cmd):
        return False, "Command contains invalid or unprintable control characters."

    # Validate against Git command allowlist
    if not any(cmd.startswith(prefix) for prefix in ALLOWED_PREFIXES):
        allowed_list_str = ", ".join(ALLOWED_PREFIXES)
        return (
            False,
            f"Command '{cmd}' is not in the allowed Git command whitelist. "
            f"Allowed command prefixes: {allowed_list_str}",
        )

    return True, cmd


def _simulate_lint_logs(code: str) -> tuple[str, str]:
    """Return (status, log_output) for a lint job."""
    code = sanitize_input_string(code)
    issues = []

    if "import *" in code:
        issues.append("W0401 Wildcard import used – avoid importing *")
    if re.search(r"except\s*:", code):
        issues.append("W0702 Bare 'except' clause catches all exceptions – be specific")
    if re.search(r"\bprint\b", code) and "def " in code:
        issues.append("T201 'print' found – consider using a logger instead")
    if re.search(r"\s+$", code, re.MULTILINE):
        issues.append("W291 Trailing whitespace detected on one or more lines")
    if re.search(r"TODO|FIXME|HACK", code):
        issues.append("W0511 TODO/FIXME comment found in code")

    if issues:
        log_lines = ["Running flake8 / pylint...", ""]
        for i, issue in enumerate(issues, 1):
            log_lines.append(f"  Line ~{random.randint(5, 80)}: {issue}")
        log_lines += ["", f"Found {len(issues)} issue(s). Fix before merging.", ""]
        return "failed", sanitize_log_output("\n".join(log_lines))
    else:
        log = "Running flake8 / pylint...\n\nAll checks passed. No lint issues found.\n"
        return "success", sanitize_log_output(log)


def _simulate_test_logs(code: str) -> tuple[str, str]:
    """Return (status, log_output) for a test job."""
    code = sanitize_input_string(code)
    has_syntax_error = code.count("(") != code.count(")")
    has_undefined = re.search(r"\bundefined_var\b|\bNULL\b", code)

    if has_syntax_error or has_undefined:
        log = (
            "Running pytest...\n\n"
            "FAILED tests/test_sandbox.py::test_submission - SyntaxError\n\n"
            "  File 'submission.py', line ...\n"
            "    SyntaxError: unexpected EOF while parsing\n\n"
            "1 failed in 0.42s\n"
        )
        return "failed", sanitize_log_output(log)

    passed = random.randint(3, 8)
    log = (
        f"Running pytest...\n\n"
        f"collected {passed} items\n\n"
        f"{'.' * passed}\n\n"
        f"{passed} passed in {random.uniform(0.2, 1.5):.2f}s\n"
    )
    return "success", sanitize_log_output(log)


def _simulate_security_logs(code: str) -> tuple[str, str]:
    """Return (status, log_output) for a security audit job."""
    code = sanitize_input_string(code)
    issues = []

    if re.search(r"eval\s*\(", code):
        issues.append("HIGH   Use of eval() detected – potential code injection")
    if re.search(r"os\.system|subprocess\.call", code):
        issues.append("MEDIUM Shell injection risk – use subprocess.run with list args")
    if re.search(r"pickle\.loads?", code):
        issues.append(
            "HIGH   Unsafe deserialization via pickle – never deserialize untrusted data"
        )
    if re.search(r"password\s*=\s*['\"]", code, re.IGNORECASE):
        issues.append("CRITICAL Hardcoded credential detected in source code")

    if issues:
        log_lines = ["Running bandit security audit...", ""]
        for issue in issues:
            log_lines.append(f"  >> {issue}")
        log_lines += [
            "",
            f"Security audit found {len(issues)} issue(s). Please review.",
            "",
        ]
        return "failed", sanitize_log_output("\n".join(log_lines))

    log = "Running bandit security audit...\n\nNo issues identified.\n\nTest passed: 0 issues\n"
    return "success", sanitize_log_output(log)


def run_pipeline_simulation(pipeline, code: str = "") -> None:
    """
    Simulate a full CI/CD pipeline for the given PipelineExecution instance.
    Includes input sanitization, command allowlist validation, and log output escaping.
    """
    from apps.sandbox.models import PipelineJob

    now = datetime.now(tz=timezone.utc)
    overall_status = "success"

    # Sanitize input code
    sanitized_code = sanitize_input_string(code, max_length=MAX_CODE_LENGTH)

    # Validate trigger command if provided
    is_valid_cmd, cmd_validation_msg = validate_trigger_command(
        pipeline.trigger_command or ""
    )

    if not is_valid_cmd:
        overall_status = "failed"
        log_msg = sanitize_log_output(
            f"Validation Failed for trigger command: {cmd_validation_msg}\n"
            f"Pipeline execution aborted."
        )
        PipelineJob.objects.create(
            pipeline=pipeline,
            job_type=PipelineJob.JobType.LINT,
            status="failed",
            log_output=log_msg,
            duration_seconds=0.01,
            completed_at=now,
        )
        pipeline.status = overall_status
        pipeline.completed_at = now
        pipeline.save(update_fields=["status", "completed_at"])
        return

    job_runners = [
        (PipelineJob.JobType.LINT, _simulate_lint_logs),
        (PipelineJob.JobType.TEST, _simulate_test_logs),
        (PipelineJob.JobType.SECURITY, _simulate_security_logs),
    ]

    for job_type, runner_fn in job_runners:
        status_str, log_output = runner_fn(sanitized_code)
        duration = round(random.uniform(0.5, 4.0), 2)

        PipelineJob.objects.create(
            pipeline=pipeline,
            job_type=job_type,
            status=status_str,
            log_output=sanitize_log_output(log_output),
            duration_seconds=duration,
            completed_at=now,
        )

        if status_str == "failed":
            overall_status = "failed"

    pipeline.status = overall_status
    pipeline.completed_at = now
    pipeline.save(update_fields=["status", "completed_at"])
