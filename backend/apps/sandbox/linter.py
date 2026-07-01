import difflib
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class LintResult:
    is_valid: bool
    message: Optional[str] = None


# Data-driven rules for Git subcommands
COMMAND_RULES: Dict[str, Dict[str, Any]] = {
    "status": {},
    "init": {},
    "add": {"requires_args": True},
    "commit": {"requires_message": True},
    "branch": {},
    "checkout": {"requires_args": True},
    "switch": {"requires_args": True},
    "merge": {"requires_args": True},
    "pull": {},
    "push": {},
    "clone": {"requires_args": True},
    "remote": {"subcommands": ["add", "remove", "set-url", "rename"]},
    "log": {},
}

# Regex to catch shell metacharacters and prevent injection chaining
FORBIDDEN_CHARS = re.compile(r"[;&|$\n\r<>]")


def get_hint(subcommand: str) -> str:
    """Provides a helpful hint for a specific Git subcommand."""
    hints = {
        "add": "Try: git add . to stage all files.",
        "commit": 'Use: git commit -m "your message".',
        "push": "Example: git push origin main.",
        "clone": "Example: git clone <repository-url>.",
        "checkout": "Example: git checkout <branch-name>.",
        "switch": "Example: git switch <branch-name>.",
        "merge": "Example: git merge <branch-name>.",
        "remote": "To add a remote: git remote add origin <url>.",
    }
    return hints.get(subcommand, f"Check the usage for 'git {subcommand}'.")


def lint_command(command: str) -> LintResult:
    """
    Performs basic syntax checking on a Git command string using strict lexical boundaries and rule-based validation.
    Prevents shell injection and ReDoS vulnerabilities.
    """
    normalized = command.strip()

    # 1. Hard length constraint to prevent memory exhaustion
    if len(normalized) > 200:
        return LintResult(
            is_valid=False,
            message="Command length exceeds the maximum allowed limit of 200 characters.",
        )

    # 2. Block shell execution metacharacters
    if FORBIDDEN_CHARS.search(normalized):
        return LintResult(
            is_valid=False,
            message="Shell metacharacters (;, &, |, $, etc.) are strictly prohibited.",
        )

    if not normalized:
        return LintResult(is_valid=False, message="Command cannot be empty.")

    parts = normalized.split()
    base_cmd = parts[0]

    # Check for 'git' prefix
    if base_cmd != "git":
        if base_cmd in ["gt", "get", "gti"]:
            return LintResult(
                is_valid=False, message=f"Did you mean 'git'? You typed '{base_cmd}'."
            )
        return LintResult(
            is_valid=False,
            message="All commands in this workshop should start with 'git'. For example: 'git status'.",
        )

    if len(parts) == 1:
        return LintResult(
            is_valid=False,
            message="You typed 'git' but didn't provide a sub-command. Try 'git status' to see the current state.",
        )

    sub_command = parts[1]
    args = parts[2:]

    # Use difflib for smart typo detection and verb allowlisting
    if sub_command not in COMMAND_RULES:
        suggestions = difflib.get_close_matches(
            sub_command, list(COMMAND_RULES.keys()), n=1, cutoff=0.7
        )
        if suggestions:
            return LintResult(
                is_valid=False,
                message=f"Unknown Git command '{sub_command}'. Did you mean 'git {suggestions[0]}'?",
            )
        return LintResult(
            is_valid=False,
            message=f"Git operation '{sub_command}' is restricted or invalid.",
        )

    # Rule-based validation
    rule = COMMAND_RULES[sub_command]

    # Check for required arguments
    if rule.get("requires_args") and not args:
        return LintResult(
            is_valid=False,
            message=f"The '{sub_command}' command requires additional arguments. {get_hint(sub_command)}",
        )

    # Specific check for commit message
    if rule.get("requires_message"):
        if "-m" not in args:
            return LintResult(
                is_valid=False,
                message=f"Commits usually need a message flags. {get_hint(sub_command)}",
            )
        m_index = args.index("-m")
        if m_index == len(args) - 1 or not args[m_index + 1].strip():
            return LintResult(
                is_valid=False,
                message=f"You provided the -m flag but no message. {get_hint(sub_command)}",
            )

    # Specific check for remote subcommands
    if sub_command == "remote" and args:
        sub_sub_command = args[0]
        if sub_sub_command == "add" and len(args) < 3:
            return LintResult(
                is_valid=False,
                message=f"To add a remote, you need a name and a URL. {get_hint(sub_command)}",
            )

    return LintResult(is_valid=True)
