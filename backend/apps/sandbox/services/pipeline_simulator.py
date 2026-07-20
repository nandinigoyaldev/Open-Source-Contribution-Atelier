"""
CI/CD Pipeline Simulation Service.

Generates realistic simulated console log output for each job type
based on the user's code content.
"""

import random
import re
from datetime import datetime, timezone


def _simulate_lint_logs(code: str) -> tuple[str, str]:
    """Return (status, log_output) for a lint job."""
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
        return "failed", "\n".join(log_lines)
    else:
        log = "Running flake8 / pylint...\n\nAll checks passed. No lint issues found.\n"
        return "success", log


def _simulate_test_logs(code: str) -> tuple[str, str]:
    """Return (status, log_output) for a test job."""
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
        return "failed", log

    passed = random.randint(3, 8)
    log = (
        f"Running pytest...\n\n"
        f"collected {passed} items\n\n"
        f"{'.' * passed}\n\n"
        f"{passed} passed in {random.uniform(0.2, 1.5):.2f}s\n"
    )
    return "success", log


def _simulate_security_logs(code: str) -> tuple[str, str]:
    """Return (status, log_output) for a security audit job."""
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
        return "failed", "\n".join(log_lines)

    log = "Running bandit security audit...\n\nNo issues identified.\n\nTest passed: 0 issues\n"
    return "success", log


def run_pipeline_simulation(pipeline, code: str = "") -> None:
    """
    Simulate a full CI/CD pipeline for the given PipelineExecution instance.
    """
    from apps.sandbox.models import PipelineJob

    now = datetime.now(tz=timezone.utc)
    overall_status = "success"

    job_runners = [
        (PipelineJob.JobType.LINT, _simulate_lint_logs),
        (PipelineJob.JobType.TEST, _simulate_test_logs),
        (PipelineJob.JobType.SECURITY, _simulate_security_logs),
    ]

    for job_type, runner_fn in job_runners:
        status_str, log_output = runner_fn(code)
        duration = round(random.uniform(0.5, 4.0), 2)

        PipelineJob.objects.create(
            pipeline=pipeline,
            job_type=job_type,
            status=status_str,
            log_output=log_output,
            duration_seconds=duration,
            completed_at=now,
        )

        if status_str == "failed":
            overall_status = "failed"

    pipeline.status = overall_status
    pipeline.completed_at = now
    pipeline.save(update_fields=["status", "completed_at"])
