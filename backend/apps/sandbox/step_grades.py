from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from apps.sandbox.ast_verifier import ASTVerifier, parse_git_command


@dataclass
class StepGrade:
    """Grade details for an individual step in a sandbox exercise."""

    step_index: int
    expected_command: str
    executed_command: Optional[str] = None
    score: float = 0.0
    status: str = "failed"  # "passed", "partial", "failed", "forbidden"
    hint: str = ""


@dataclass
class StepGradingResult:
    """Overall grading result for a multi-step sandbox session."""

    total_score: float
    max_score: float
    percentage: float
    step_grades: List[StepGrade] = field(default_factory=list)
    summary: str = ""


def _evaluate_equivalence(expected_cmd_str: str, executed_cmd_str: str) -> Tuple[float, Optional[str]]:
    """
    Evaluates if executed_cmd_str is functionally equivalent to expected_cmd_str.
    Returns tuple of (score_multiplier, custom_hint_override).
    """
    exp_ast = parse_git_command(expected_cmd_str)
    exc_ast = parse_git_command(executed_cmd_str)

    if not exp_ast.subcommand or not exc_ast.subcommand:
        return (0.0, None)

    exp_sub = exp_ast.subcommand.lower()
    exc_sub = exc_ast.subcommand.lower()

    # Exact subcommand and matching target args/flags
    if exp_sub == exc_sub:
        if exp_ast.args == exc_ast.args and exp_ast.flag_values == exc_ast.flag_values:
            return (1.0, None)
        if exp_ast.args == exc_ast.args and set(exp_ast.flags) == set(exc_ast.flags):
            return (1.0, None)
        # Same subcommand, slightly different args (e.g. branch name)
        return (0.8, f"Subcommand '{exp_sub}' matches, but arguments differed.")

    # Equivalent: switch vs checkout (switching branch)
    if exp_sub in ["checkout", "switch"] and exc_sub in ["checkout", "switch"]:
        if not "-b" in exp_ast.flags and not "-b" in exc_ast.flags:
            if exp_ast.args == exc_ast.args:
                return (1.0, f"Used 'git {exc_sub}' which is equivalent to 'git {exp_sub}'.")

    # Equivalent: merge vs rebase
    if exp_sub == "rebase" and exc_sub == "merge":
        return (
            0.5,
            "You used git merge but git rebase was expected (50% credit). Try using rebase to keep a linear history.",
        )
    if exp_sub == "merge" and exc_sub == "rebase":
        return (
            0.5,
            "You used git rebase but git merge was expected (50% credit). Try using merge to preserve complete commit context.",
        )

    return (0.0, None)


def grade_session(
    executed_commands: List[str],
    expected_steps: List[str],
    lesson_slug: Optional[str] = None,
    allowlist_config: Optional[dict] = None,
) -> StepGradingResult:
    """
    Compares a list of executed Git commands against expected solution steps.
    Validates every executed command against the AST allowlist engine.
    Assigns:
      - 1.0 for exact matches or valid equivalent choices
      - 0.5 for partial/functionally equivalent alternatives (e.g. merge vs rebase)
      - 0.0 for absent, incorrect, or forbidden commands
    """
    if not expected_steps:
        return StepGradingResult(
            total_score=0.0,
            max_score=0.0,
            percentage=0.0,
            step_grades=[],
            summary="No expected steps specified for exercise.",
        )

    # Pre-validate all executed commands with AST verifier for forbidden commands
    verified_events = []
    for cmd in executed_commands:
        val = ASTVerifier.verify_command(cmd, allowlist_config=allowlist_config, lesson_slug=lesson_slug)
        verified_events.append((cmd, val))

    step_grades: List[StepGrade] = []
    total_score = 0.0
    max_score = float(len(expected_steps))

    # Match executed commands to expected steps
    exc_idx = 0

    for step_num, expected_step in enumerate(expected_steps, start=1):
        step_done = False

        while exc_idx < len(verified_events):
            exec_cmd, val = verified_events[exc_idx]
            exc_idx += 1

            if not val.is_valid:
                # Forbidden or invalid command
                step_grades.append(
                    StepGrade(
                        step_index=step_num,
                        expected_command=expected_step,
                        executed_command=exec_cmd,
                        score=0.0,
                        status="forbidden",
                        hint=f"Step {step_num}: Command '{exec_cmd}' was rejected: {val.reason}",
                    )
                )
                step_done = True
                break

            # Evaluate match score
            score_factor, hint_override = _evaluate_equivalence(expected_step, exec_cmd)

            if score_factor >= 1.0:
                step_score = 1.0
                total_score += step_score
                step_grades.append(
                    StepGrade(
                        step_index=step_num,
                        expected_command=expected_step,
                        executed_command=exec_cmd,
                        score=step_score,
                        status="passed",
                        hint=hint_override or f"Step {step_num}: Passed successfully with '{exec_cmd}'.",
                    )
                )
                step_done = True
                break

            elif score_factor > 0.0:
                step_score = score_factor
                total_score += step_score
                step_grades.append(
                    StepGrade(
                        step_index=step_num,
                        expected_command=expected_step,
                        executed_command=exec_cmd,
                        score=step_score,
                        status="partial",
                        hint=hint_override or f"Step {step_num}: Partial credit ({int(step_score * 100)}%).",
                    )
                )
                step_done = True
                break

        if not step_done and (exc_idx >= len(verified_events)):
            # Missing step
            step_grades.append(
                StepGrade(
                    step_index=step_num,
                    expected_command=expected_step,
                    executed_command=None,
                    score=0.0,
                    status="failed",
                    hint=f"Step {step_num}: Missing step. Expected '{expected_step}'.",
                )
            )

    percentage = round((total_score / max_score) * 100.0, 1) if max_score > 0 else 0.0
    summary = f"Completed {len([g for g in step_grades if g.score > 0])} of {len(expected_steps)} steps ({percentage}%)."

    return StepGradingResult(
        total_score=total_score,
        max_score=max_score,
        percentage=percentage,
        step_grades=step_grades,
        summary=summary,
    )
