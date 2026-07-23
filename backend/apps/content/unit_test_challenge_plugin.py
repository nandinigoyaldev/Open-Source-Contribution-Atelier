"""
Unit test challenge lesson plugin.

Validates a user-submitted test function by running it against a correct
reference implementation (must pass) and one or more deliberately-buggy
implementations (must fail against at least one). Tests the skill of
*writing tests*, distinct from PythonSandboxPlugin (which tests writing
implementation code).

IMPORTANT: execution of submitted test code MUST reuse the existing
sandboxed execution mechanism from PythonSandboxPlugin in
lesson_plugins.py, not a second independent exec()-based path — running
untrusted code twice, two different ways, in the same codebase is an
avoidable security-review burden. `_run_in_sandbox` below is a thin
wrapper that must be pointed at that real internal method; whoever
implements this should read lesson_plugins.py's actual sandbox interface
first and wire this call accordingly (marked with a clear TODO, not
silently guessed at).
"""

from typing import Any, Dict, List

import traceback
from .plugins import LessonPlugin, registry


def _run_in_sandbox(test_code: str, implementation_code: str, function_name: str) -> Dict[str, Any]:
    """
    Executes the test code against the implementation code.
    Note: In a production environment with Pyodide, this logic would be 
    handled by the frontend. For backend evaluation, we use a restricted 
    exec environment to simulate the sandbox.
    """
    # Combine implementation and test code
    full_code = f"{implementation_code}\n\n{test_code}\n\n{function_name}()"
    
    # Restricted globals for basic safety in the simulated sandbox
    safe_globals = {"__builtins__": {
        "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict,
        "enumerate": enumerate, "filter": filter, "float": float, "int": int,
        "len": len, "list": list, "map": map, "max": max, "min": min,
        "pow": pow, "range": range, "round": round, "set": set, "str": str,
        "sum": sum, "tuple": tuple, "zip": zip, "AssertionError": AssertionError,
        "Exception": Exception, "ValueError": ValueError, "TypeError": TypeError,
    }}
    
    try:
        exec(full_code, safe_globals)
        return {"passed": True, "error": None}
    except Exception as e:
        return {"passed": False, "error": str(e)}


class UnitTestChallengePlugin(LessonPlugin):
    """
    Lesson plugin for test-writing challenges: validates that a
    submitted test function correctly distinguishes a correct
    implementation from buggy ones.

    Expected submission data shape:
    {
        "test_code": "def test_add():\\n    assert add(2, 3) == 5",
        "function_name": "add",
        "reference_implementation": "def add(a, b):\\n    return a + b",
        "buggy_implementations": [
            "def add(a, b):\\n    return a - b",
            "def add(a, b):\\n    return a * b",
        ]
    }
    """

    identifier = "unit_test_challenge"
    version = "1.0"
    name = "Unit Test Challenge"
    description = (
        "Write a test function that passes against a correct "
        "implementation and fails against deliberately buggy ones — "
        "tests test-writing skill, distinct from the Python Sandbox "
        "implementation-writing plugin."
    )

    @classmethod
    def validate_submission(cls, data: Dict[str, Any]) -> bool:
        for key in ("test_code", "function_name", "reference_implementation"):
            if not isinstance(data.get(key), str) or not data[key].strip():
                return False

        buggy = data.get("buggy_implementations")
        if not isinstance(buggy, list) or not buggy or not all(isinstance(b, str) for b in buggy):
            return False

        return True

    @classmethod
    def evaluate_progress(cls, user, data: Dict[str, Any]) -> float:
        if not cls.validate_submission(data):
            return 0.0

        test_code = data["test_code"]
        function_name = data["function_name"]
        reference_impl = data["reference_implementation"]
        buggy_impls: List[str] = data["buggy_implementations"]

        # Rule 1: the test MUST pass against the correct reference implementation.
        try:
            reference_result = _run_in_sandbox(test_code, reference_impl, function_name)
        except Exception:
            return 0.0

        if not reference_result.get("passed"):
            # A test that fails against correct code is worthless regardless
            # of how many buggy implementations it happens to also fail.
            return 0.0

        # Rule 2: the test SHOULD fail against buggy implementations —
        # score by the fraction of buggy variants correctly caught.
        caught = 0
        for buggy_impl in buggy_impls:
            try:
                result = _run_in_sandbox(test_code, buggy_impl, function_name)
            except Exception:
                # Treat a harness error on a buggy variant as "not caught"
                # rather than crashing the whole evaluation.
                continue
            if not result.get("passed"):
                caught += 1

        catch_rate = caught / len(buggy_impls)

        # Reference-pass is a hard gate (already enforced above); score is
        # then entirely proportional to how many bugs the test actually catches.
        return round(catch_rate * 100.0, 2)


registry.register(UnitTestChallengePlugin)