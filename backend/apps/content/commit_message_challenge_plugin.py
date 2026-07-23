"""
Commit message challenge lesson plugin.

Validates a user-submitted commit message against Conventional Commits
rules (type(scope): description), matching this repository's own
CONTRIBUTING.md convention. Scores by percentage of individual rules
satisfied, and returns which specific rules failed so learners get
actionable feedback rather than a bare pass/fail.
"""

import re
from typing import Any, Dict, List, Tuple

from .plugins import LessonPlugin, registry

_DEFAULT_ALLOWED_TYPES = (
    "feat", "fix", "docs", "style", "refactor",
    "perf", "test", "chore", "ci", "build",
)

# type(optional-scope): description
_HEADER_PATTERN = re.compile(
    r"^(?P<type>[a-z]+)(\((?P<scope>[a-z0-9_\-\.]+)\))?: (?P<description>.+)$"
)

_COMMON_NON_IMPERATIVE_SUFFIXES = ("ed", "ing")


def _looks_imperative(description: str) -> bool:
    """
    Heuristic check that the first word of the description is likely
    imperative mood (e.g. "add X" not "added X" / "adding X"). This is a
    heuristic, not a grammatical guarantee — flagged as such in scoring
    (contributes partial credit, not a hard pass/fail gate), since full
    imperative-mood detection needs real NLP and would be overkill here.
    """
    first_word = description.strip().split(" ", 1)[0].lower() if description.strip() else ""
    if not first_word:
        return False
    return not first_word.endswith(_COMMON_NON_IMPERATIVE_SUFFIXES)


def _evaluate_rules(message: str, allowed_types: Tuple[str, ...]) -> List[Tuple[str, bool]]:
    """
    Evaluate a commit message header against Conventional Commits rules.
    Returns a list of (rule_name, passed) tuples.
    """
    header = message.strip().split("\n", 1)[0]
    match = _HEADER_PATTERN.match(header)

    rules: List[Tuple[str, bool]] = []

    rules.append(("has_valid_structure", match is not None))

    if not match:
        # Can't evaluate further rules without a parseable structure
        return rules

    commit_type = match.group("type")
    scope = match.group("scope")
    description = match.group("description")

    rules.append(("type_is_allowed", commit_type in allowed_types))
    rules.append(("has_description", bool(description and description.strip())))
    rules.append(("description_not_empty_after_colon", description != "" and not description.isspace()))
    rules.append(("description_no_trailing_period", not description.rstrip().endswith(".")))
    rules.append(("description_reasonable_length", len(description) <= 72))
    rules.append(("description_starts_lowercase", description[:1].islower() if description else False))
    rules.append(("description_looks_imperative", _looks_imperative(description)))

    if scope is not None:
        rules.append(("scope_format_valid", bool(re.match(r"^[a-z0-9_\-\.]+$", scope))))

    return rules


class CommitMessageChallengePlugin(LessonPlugin):
    """
    Lesson plugin for Conventional Commits message-writing challenges.

    Expected submission data shape:
    {
        "commit_message": "feat(auth): add Google OAuth login",
        "allowed_types": ["feat", "fix", "docs"]   # optional override
    }
    """

    identifier = "commit_message_challenge"
    version = "1.0"
    name = "Commit Message Challenge"
    description = (
        "Write a commit message following Conventional Commits format "
        "(matching this repository's own CONTRIBUTING.md convention), "
        "scored by percentage of individual formatting rules satisfied."
    )

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        base = super().get_metadata()
        base["default_allowed_types"] = list(_DEFAULT_ALLOWED_TYPES)
        return base

    @classmethod
    def validate_submission(cls, data: Dict[str, Any]) -> bool:
        message = data.get("commit_message")
        if not isinstance(message, str) or not message.strip():
            return False

        allowed_types = data.get("allowed_types")
        if allowed_types is not None:
            if not isinstance(allowed_types, list) or not all(isinstance(t, str) for t in allowed_types):
                return False

        return True

    @classmethod
    def evaluate_progress(cls, user, data: Dict[str, Any]) -> float:
        if not cls.validate_submission(data):
            return 0.0

        message = data["commit_message"]
        allowed_types = tuple(data.get("allowed_types") or _DEFAULT_ALLOWED_TYPES)

        rule_results = _evaluate_rules(message, allowed_types)

        if not rule_results:
            return 0.0

        passed = sum(1 for _, ok in rule_results if ok)
        total = len(rule_results)

        return round((passed / total) * 100.0, 2)

    @classmethod
    def get_rule_breakdown(cls, data: Dict[str, Any]) -> List[Tuple[str, bool]]:
        """
        Non-interface helper: returns the per-rule pass/fail breakdown for
        a submission, for surfacing specific feedback to the learner
        (e.g. "description_no_trailing_period: FAILED") beyond just the
        aggregate score from evaluate_progress.
        """
        if not cls.validate_submission(data):
            return []
        message = data["commit_message"]
        allowed_types = tuple(data.get("allowed_types") or _DEFAULT_ALLOWED_TYPES)
        return _evaluate_rules(message, allowed_types)


registry.register(CommitMessageChallengePlugin)
