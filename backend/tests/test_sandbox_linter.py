import pytest

from apps.sandbox.linter import lint_command


def test_lint_empty_command():
    result = lint_command("")
    assert not result.is_valid
    assert result.message == "Command cannot be empty."

    result = lint_command("   ")
    assert not result.is_valid
    assert result.message == "Command cannot be empty."


def test_lint_missing_git_prefix():
    result = lint_command("status")
    assert not result.is_valid
    assert "All commands in this workshop should start with 'git'" in result.message


def test_lint_common_prefix_typos():
    result = lint_command("gt status")
    assert not result.is_valid
    assert "Did you mean 'git'?" in result.message

    result = lint_command("get add .")
    assert not result.is_valid
    assert "Did you mean 'git'?" in result.message


def test_lint_git_only():
    result = lint_command("git")
    assert not result.is_valid
    assert "didn't provide a sub-command" in result.message


def test_lint_git_add_missing_args():
    result = lint_command("git add")
    assert not result.is_valid
    assert "requires additional arguments" in result.message
    assert "git add ." in result.message


def test_lint_git_commit_missing_args():
    result = lint_command("git commit")
    assert not result.is_valid
    assert "usually need a message" in result.message

    result = lint_command("git commit -m")
    assert not result.is_valid
    assert "provided the -m flag but no message" in result.message

    result = lint_command("git commit 'initial commit'")
    assert not result.is_valid
    assert "need a message flag" in result.message


def test_lint_git_subcommand_typo_suggestions():
    # Test difflib suggestions
    result = lint_command("git stats")
    assert not result.is_valid
    assert "Did you mean 'git status'?" in result.message

    result = lint_command("git commot")
    assert not result.is_valid
    assert "Did you mean 'git commit'?" in result.message

    result = lint_command("git checkot")
    assert not result.is_valid
    assert "Did you mean 'git checkout'?" in result.message


def test_lint_git_checkout_missing_args():
    result = lint_command("git checkout")
    assert not result.is_valid
    assert "requires additional arguments" in result.message
    assert "git checkout <branch-name>" in result.message


def test_lint_git_clone_missing_args():
    result = lint_command("git clone")
    assert not result.is_valid
    assert "requires additional arguments" in result.message
    assert "git clone <repository-url>" in result.message


def test_lint_valid_commands():
    valid_commands = [
        "git status",
        "git add .",
        "git add file.txt",
        "git commit -m 'feat: add linter'",
        "git checkout main",
        "git branch",
        "git log",
        "git remote add origin https://github.com/user/repo.git",
    ]
    for cmd in valid_commands:
        result = lint_command(cmd)
        assert result.is_valid, f"Command should be valid: {cmd}"
