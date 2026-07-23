"""
Code analysis service using AST parsing.
"""

import ast
import re
import builtins
from typing import List, Dict, Any, Tuple
import radon.complexity as radon_complexity
from radon.visitors import ComplexityVisitor
import pycodestyle
from apps.pr_review_bot.models import CodeIssue
import logging

logger = logging.getLogger(__name__)


class CodeAnalyzer:
    """
    Analyze code for quality issues using AST.
    """

    def __init__(self):
        self.issues = []

    def analyze_python_code(self, code: str, file_path: str) -> List[Dict]:
        """
        Analyze Python code for issues.
        """
        self.issues = []

        # Style checks (PEP 8)
        self._check_style(code, file_path)

        # Complexity checks
        self._check_complexity(code, file_path)

        # Duplication checks
        self._check_duplication(code, file_path)

        # Security checks
        self._check_security(code, file_path)

        # Performance checks
        self._check_performance(code, file_path)

        return self.issues

    def _check_style(self, code: str, file_path: str):
        """Check code style using pycodestyle."""
        try:
            style_checker = pycodestyle.Checker(filename=file_path)
            errors = style_checker.check_all()

            if errors:
                self.issues.append(
                    {
                        "type": "style",
                        "severity": "warning",
                        "title": "Style issues detected",
                        "description": f"Found {errors} style violations",
                        "file_path": file_path,
                        "suggestion": "Run black or autopep8 to fix style issues",
                    }
                )
        except Exception as e:
            logger.error(f"Style check failed: {e}")

    def _check_complexity(self, code: str, file_path: str):
        """Check code complexity using Radon."""
        try:
            visitor = ComplexityVisitor.from_code(code)
            complex_functions = []

            for func in visitor.functions:
                if func.complexity > 10:
                    complex_functions.append(func)

            if complex_functions:
                for func in complex_functions:
                    self.issues.append(
                        {
                            "type": "complexity",
                            "severity": "warning" if func.complexity <= 20 else "error",
                            "title": f"Function '{func.name}' is too complex",
                            "description": f"Cyclomatic complexity: {func.complexity} (max: 10)",
                            "file_path": file_path,
                            "line_number": func.lineno,
                            "code_snippet": self._get_code_snippet(code, func.lineno),
                            "suggestion": f"Refactor '{func.name}' into smaller functions",
                            "suggested_code": self._suggest_refactor(code, func),
                        }
                    )
        except Exception as e:
            logger.error(f"Complexity check failed: {e}")

    def _check_duplication(self, code: str, file_path: str):
        """Check for code duplication."""
        # Simplified duplication check
        lines = code.split("\n")
        line_groups = {}

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and len(stripped) > 20:  # Only check meaningful lines
                if stripped in line_groups:
                    line_groups[stripped].append(i)
                else:
                    line_groups[stripped] = [i]

        duplicates = {k: v for k, v in line_groups.items() if len(v) > 2}

        if duplicates:
            dup_count = len(duplicates)
            self.issues.append(
                {
                    "type": "duplication",
                    "severity": "warning" if dup_count < 5 else "error",
                    "title": f"Duplicate code detected",
                    "description": f"Found {dup_count} duplicate code blocks",
                    "file_path": file_path,
                    "suggestion": "Extract duplicate code into reusable functions",
                    "suggested_code": self._suggest_extract_function(duplicates),
                }
            )

    def _check_security(self, code: str, file_path: str):
        """Check for security issues."""
        security_patterns = [
            (r"eval\(", "Avoid using eval() - it can execute arbitrary code"),
            (r"exec\(", "Avoid using exec() - it can execute arbitrary code"),
            (r"__import__\(", "Avoid dynamic imports - they can be dangerous"),
            (r"os\.system\(", "Avoid os.system() - use subprocess instead"),
            (
                r"subprocess\.call\(shell=True",
                "Avoid shell=True in subprocess - it's a security risk",
            ),
            (r"password|secret|key.*=", "Hardcoded credentials detected!"),
            (r"sql.*SELECT.*\+", "Potential SQL injection - use parameterized queries"),
        ]

        for pattern, message in security_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                self.issues.append(
                    {
                        "type": "security",
                        "severity": "critical",
                        "title": "Security issue detected",
                        "description": message,
                        "file_path": file_path,
                        "suggestion": f"Fix: {message}",
                    }
                )

    def _check_performance(self, code: str, file_path: str):
        """Check for performance issues."""
        performance_patterns = [
            (
                r"for\s+.*\s+in\s+range\(len\(",
                "Nested loops with range(len()) - use enumerate()",
            ),
            (
                r"while\s+True:\s*\n\s*.*\n\s*break",
                "Potential infinite loop - check condition",
            ),
            (
                r"\.append\(.*\)\s*for",
                "Consider using list comprehension for better performance",
            ),
        ]

        for pattern, message in performance_patterns:
            if re.search(pattern, code, re.DOTALL):
                self.issues.append(
                    {
                        "type": "performance",
                        "severity": "warning",
                        "title": "Performance issue detected",
                        "description": message,
                        "file_path": file_path,
                        "suggestion": message,
                    }
                )

    def _get_code_snippet(self, code: str, line_num: int) -> str:
        """Get code snippet around a line."""
        lines = code.split("\n")
        start = max(0, line_num - 2)
        end = min(len(lines), line_num + 3)
        return "\n".join(lines[start:end])

    def _suggest_refactor(self, code: str, func) -> str:
        """Suggest refactoring for complex function."""
        # Simplified: just suggest splitting
        return f"# Consider splitting {func.name} into smaller functions\n# Current complexity: {func.complexity}"

    def _suggest_extract_function(self, duplicates: Dict) -> str:
        """Suggest extracting duplicate code."""
        return "# Consider extracting repeated code into a reusable function"
