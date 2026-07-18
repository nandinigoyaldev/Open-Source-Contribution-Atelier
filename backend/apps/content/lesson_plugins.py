from typing import Dict, Any
from .plugins import LessonPlugin, registry


class PythonSandboxPlugin(LessonPlugin):
    identifier = "python_sandbox"
    version = "1.0"
    name = "Interactive Python Sandbox"
    description = "Executes Python code safely using Pyodide in the browser."

    @classmethod
    def validate_submission(cls, data: Dict[str, Any]) -> bool:
        code = data.get("code", "")
        return bool(code.strip())


class QuizPlugin(LessonPlugin):
    identifier = "quiz"
    version = "1.2"
    name = "Multiple Choice Quiz"
    description = "Validates standard text-based multiple choice quizzes."

    @classmethod
    def evaluate_progress(cls, user, data: Dict[str, Any]) -> float:
        # Custom quiz scoring logic here
        return 100.0 if data.get("is_correct") else 0.0


# Self-register plugins
registry.register(PythonSandboxPlugin)
registry.register(QuizPlugin)
