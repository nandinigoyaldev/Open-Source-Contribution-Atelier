from dataclasses import dataclass

ALLOWED_PREFIXES = (
    "git status",
    "git init",
    "git add",
    "git commit",
    "git branch",
    "git checkout",
    "git switch",
    "git merge",
    "git pull",
    "git push",
    "git clone",
    "git remote",
    "git log",
)


from .linter import lint_command


@dataclass
class VerificationResult:
    accepted: bool
    feedback: str
    score_delta: int


def verify_git_command(command: str, expected_command: str) -> VerificationResult:
    normalized = command.strip()
    expected = expected_command.strip()

    # Perform syntax checking / linting before validation
    lint_result = lint_command(normalized)
    if not lint_result.is_valid:
        return VerificationResult(
            accepted=False,
            feedback=lint_result.message,
            score_delta=0,
        )

    if not any(normalized.startswith(prefix) for prefix in ALLOWED_PREFIXES):
        return VerificationResult(
            accepted=False,
            feedback="That command is outside the safe learning sandbox. Try a Git command from the lesson prompt.",
            score_delta=0,
        )

    if normalized == expected:
        return VerificationResult(
            accepted=True,
            feedback="Correct command. Nice work progressing through the workflow.",
            score_delta=10,
        )

    return VerificationResult(
        accepted=False,
        feedback=f"Valid Git syntax, but not the expected command for this exercise. Hint: Try '{expected}'.",
        score_delta=0,
    )
