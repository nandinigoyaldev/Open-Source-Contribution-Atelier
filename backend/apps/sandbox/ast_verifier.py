import os
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml


@dataclass
class GitASTNode:
    """AST node representation of a tokenized Git command."""

    raw_command: str
    base_cmd: str = "git"
    subcommand: Optional[str] = None
    args: List[str] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)
    flag_values: Dict[str, Optional[str]] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Outcome of verifying a Git command against an allowlist."""

    is_valid: bool
    reason: Optional[str] = None
    ast_node: Optional[GitASTNode] = None


def parse_git_command(command_str: str) -> GitASTNode:
    """
    Tokenizes a command string into a structured GitASTNode using shlex lexical parsing.
    Handles flags (e.g., -m, --force, --branch=feat), positional arguments, and values.
    """
    normalized = command_str.strip()
    if not normalized:
        return GitASTNode(raw_command=command_str, base_cmd="")

    try:
        tokens = shlex.split(normalized)
    except ValueError:
        # Fallback for unclosed quotes or syntax errors
        tokens = normalized.split()

    if not tokens:
        return GitASTNode(raw_command=command_str, base_cmd="")

    base_cmd = tokens[0]
    if base_cmd != "git" and len(tokens) > 1 and tokens[0] != "git":
        # Handle command string without 'git' prefix if needed
        subcommand = tokens[0]
        arg_tokens = tokens[1:]
    elif len(tokens) > 1 and base_cmd == "git":
        subcommand = tokens[1]
        arg_tokens = tokens[2:]
    else:
        subcommand = None
        arg_tokens = []

    args: List[str] = []
    flags: List[str] = []
    flag_values: Dict[str, Optional[str]] = {}

    idx = 0
    while idx < len(arg_tokens):
        token = arg_tokens[idx]
        if token.startswith("-"):
            if "=" in token:
                flag_name, flag_val = token.split("=", 1)
                flags.append(flag_name)
                flag_values[flag_name] = flag_val
            else:
                flag_name = token
                flags.append(flag_name)
                # If next token exists and is not a flag, treat as flag value (e.g., -m "msg" or -b "branch")
                if idx + 1 < len(arg_tokens) and not arg_tokens[idx + 1].startswith("-"):
                    flag_values[flag_name] = arg_tokens[idx + 1]
                    idx += 1
                else:
                    flag_values[flag_name] = None
        else:
            args.append(token)
        idx += 1

    return GitASTNode(
        raw_command=command_str,
        base_cmd=base_cmd,
        subcommand=subcommand,
        args=args,
        flags=flags,
        flag_values=flag_values,
    )


class ASTVerifier:
    """
    Validates Git commands against per-lesson structured YAML allowlist DSL configurations.
    Enforces subcommand permissions, argument constraints, regex patterns, and denied flags.
    """

    _allowlist_cache: Dict[str, dict] = {}
    _ALLOWLIST_DIR = Path(__file__).parent / "allowlist"

    @classmethod
    def load_allowlist(cls, lesson_slug: Optional[str] = None) -> dict:
        """
        Loads the YAML allowlist specification for a given lesson_slug.
        Falls back to default.yml if lesson-specific config is missing.
        """
        slug = lesson_slug or "default"
        if slug in cls._allowlist_cache:
            return cls._allowlist_cache[slug]

        file_path = cls._ALLOWLIST_DIR / f"{slug}.yml"
        if not file_path.exists():
            file_path = cls._ALLOWLIST_DIR / "default.yml"

        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f) or {}
                cls._allowlist_cache[slug] = config
                return config
            except Exception:
                pass

        # Default fallback structure if file reading fails
        default_config = {
            "allowed_commands": {
                "status": {},
                "init": {},
                "add": {},
                "commit": {},
                "branch": {},
                "checkout": {},
                "switch": {},
                "merge": {},
                "rebase": {},
                "log": {},
                "pull": {},
                "push": {},
            },
            "denied_flags": ["--force", "-f", "--hard"],
        }
        cls._allowlist_cache[slug] = default_config
        return default_config

    @classmethod
    def verify_command(
        cls,
        command_str: str,
        allowlist_config: Optional[dict] = None,
        lesson_slug: Optional[str] = None,
    ) -> ValidationResult:
        """
        Verifies a command string against an allowlist configuration or lesson_slug.
        """
        ast = parse_git_command(command_str)

        if not ast.raw_command.strip():
            return ValidationResult(
                is_valid=False, reason="Command cannot be empty.", ast_node=ast
            )

        if ast.base_cmd != "git":
            return ValidationResult(
                is_valid=False,
                reason=f"Command must start with 'git'. Got '{ast.base_cmd}'.",
                ast_node=ast,
            )

        if not ast.subcommand:
            return ValidationResult(
                is_valid=False,
                reason="No Git subcommand provided. Try 'git status'.",
                ast_node=ast,
            )

        config = allowlist_config or cls.load_allowlist(lesson_slug)
        allowed_cmds = config.get("allowed_commands", {})
        global_denied_flags = set(config.get("denied_flags", ["--force", "-f", "--hard"]))

        # 1. Check for denied flags (global)
        for flag in ast.flags:
            if flag in global_denied_flags:
                return ValidationResult(
                    is_valid=False,
                    reason=f"Flag '{flag}' is forbidden for security and safety reasons.",
                    ast_node=ast,
                )

        # 2. Check subcommand authorization
        subcmd = ast.subcommand.lower()
        if subcmd not in allowed_cmds:
            return ValidationResult(
                is_valid=False,
                reason=f"Git command 'git {subcmd}' is not allowed for this exercise.",
                ast_node=ast,
            )

        cmd_spec = allowed_cmds.get(subcmd) or {}

        # 3. Check subcommand-specific denied flags
        spec_denied_flags = set(cmd_spec.get("denied_flags", []))
        for flag in ast.flags:
            if flag in spec_denied_flags:
                return ValidationResult(
                    is_valid=False,
                    reason=f"Flag '{flag}' is not allowed for 'git {subcmd}'.",
                    ast_node=ast,
                )

        # 4. Check required flags
        required_flags = cmd_spec.get("required_flags", [])
        for req_flag in required_flags:
            if req_flag not in ast.flags:
                return ValidationResult(
                    is_valid=False,
                    reason=f"Command 'git {subcmd}' requires flag '{req_flag}'.",
                    ast_node=ast,
                )

        # 5. Check positional argument count rules
        args_count_spec = cmd_spec.get("args_count")
        if isinstance(args_count_spec, dict):
            min_args = args_count_spec.get("min")
            max_args = args_count_spec.get("max")
            exact_args = args_count_spec.get("exact")

            num_args = len(ast.args)
            if ast.flags and not ast.args:
                num_args += len([v for v in ast.flag_values.values() if v is not None])

            if exact_args is not None and num_args != exact_args:
                return ValidationResult(
                    is_valid=False,
                    reason=f"'git {subcmd}' expects exactly {exact_args} argument(s), got {num_args}.",
                    ast_node=ast,
                )
            if min_args is not None and num_args < min_args:
                return ValidationResult(
                    is_valid=False,
                    reason=f"'git {subcmd}' requires at least {min_args} argument(s).",
                    ast_node=ast,
                )
            if max_args is not None and num_args > max_args:
                return ValidationResult(
                    is_valid=False,
                    reason=f"'git {subcmd}' accepts at most {max_args} argument(s).",
                    ast_node=ast,
                )
        elif isinstance(cmd_spec.get("args"), int):
            expected = cmd_spec["args"]
            num_args = len(ast.args) + (len([v for v in ast.flag_values.values() if v is not None]) if ast.flags and not ast.args else 0)
            if num_args != expected:
                return ValidationResult(
                    is_valid=False,
                    reason=f"'git {subcmd}' expects {expected} argument(s), got {num_args}.",
                    ast_node=ast,
                )

        # 6. Check argument regex pattern
        pattern = cmd_spec.get("pattern")
        if pattern and ast.args:
            first_arg = ast.args[0]
            if not re.search(pattern, first_arg):
                return ValidationResult(
                    is_valid=False,
                    reason=f"Argument '{first_arg}' does not match expected format pattern '{pattern}'.",
                    ast_node=ast,
                )

        return ValidationResult(is_valid=True, reason=None, ast_node=ast)
