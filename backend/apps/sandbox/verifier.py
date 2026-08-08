from typing import Any, Dict, List, Optional, Union

from apps.sandbox.ast_verifier import ASTVerifier, parse_git_command
from apps.sandbox.history_capture import HistoryEvent, parse_terminal_session
from apps.sandbox.step_grades import StepGradingResult, grade_session


class SandboxVerifier:
    """
    Unified entry point for sandbox exercise evaluation.
    Captures session history, runs AST-based allowlist verification, and grades step execution.
    """

    @classmethod
    def verify_single_command(
        cls, command_str: str, lesson_slug: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Verifies a single Git command against the AST allowlist.
        """
        val_result = ASTVerifier.verify_command(command_str, lesson_slug=lesson_slug)
        return {
            "is_valid": val_result.is_valid,
            "reason": val_result.reason,
            "ast": {
                "subcommand": val_result.ast_node.subcommand if val_result.ast_node else None,
                "args": val_result.ast_node.args if val_result.ast_node else [],
                "flags": val_result.ast_node.flags if val_result.ast_node else [],
            }
            if val_result.ast_node
            else None,
        }

    @classmethod
    def evaluate_session(
        cls,
        session_log: Union[str, List[Union[str, Dict[str, Any]]]],
        expected_steps: List[str],
        lesson_slug: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Parses a full terminal session log, extracts executed Git commands,
        and grades the session against expected steps using AST allowlisting and per-step rules.
        """
        events: List[HistoryEvent] = parse_terminal_session(session_log)
        executed_commands = [evt.command for evt in events if evt.command]

        grading: StepGradingResult = grade_session(
            executed_commands=executed_commands,
            expected_steps=expected_steps,
            lesson_slug=lesson_slug,
        )

        return {
            "total_score": grading.total_score,
            "max_score": grading.max_score,
            "percentage": grading.percentage,
            "passed": grading.percentage >= 100.0,
            "summary": grading.summary,
            "steps": [
                {
                    "step_index": step.step_index,
                    "expected_command": step.expected_command,
                    "executed_command": step.executed_command,
                    "score": step.score,
                    "status": step.status,
                    "hint": step.hint,
                }
                for step in grading.step_grades
            ],
        }
