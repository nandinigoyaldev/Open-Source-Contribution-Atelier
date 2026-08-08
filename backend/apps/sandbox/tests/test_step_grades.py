from django.test import TestCase

from apps.sandbox.history_capture import parse_terminal_session
from apps.sandbox.step_grades import grade_session
from apps.sandbox.verifier import SandboxVerifier


class StepGradesTests(TestCase):
    def test_grade_session_exact_match(self):
        executed = [
            "git checkout -b feature-auth",
            'git commit -m "feat: login form"',
            "git checkout main",
            "git merge feature-auth",
        ]
        expected = [
            "git checkout -b feature-auth",
            'git commit -m "feat: login form"',
            "git checkout main",
            "git merge feature-auth",
        ]

        result = grade_session(executed, expected)
        self.assertEqual(result.total_score, 4.0)
        self.assertEqual(result.percentage, 100.0)
        self.assertEqual(len(result.step_grades), 4)
        for step in result.step_grades:
            self.assertEqual(step.status, "passed")

    def test_grade_session_partial_credit_equivalence(self):
        # User executed merge when rebase was expected
        executed = ["git merge main"]
        expected = ["git rebase main"]

        result = grade_session(executed, expected, lesson_slug="merge-vs-rebase")
        self.assertEqual(result.total_score, 0.5)
        self.assertEqual(result.percentage, 50.0)
        self.assertEqual(result.step_grades[0].status, "partial")
        self.assertIn("50% credit", result.step_grades[0].hint)

    def test_grade_session_forbidden_command(self):
        executed = ["git push --force origin main"]
        expected = ["git push origin main"]

        result = grade_session(executed, expected)
        self.assertEqual(result.total_score, 0.0)
        self.assertEqual(result.percentage, 0.0)
        self.assertEqual(result.step_grades[0].status, "forbidden")
        self.assertIn("forbidden", result.step_grades[0].hint)

    def test_sandbox_verifier_session_evaluation(self):
        raw_log = """
$ git status
$ git checkout -b feature-ui
$ git add .
$ git commit -m "add navigation UI"
        """
        expected = [
            "git checkout -b feature-ui",
            "git add .",
            'git commit -m "add navigation UI"',
        ]

        res = SandboxVerifier.evaluate_session(raw_log, expected)
        self.assertTrue(res["passed"])
        self.assertEqual(res["total_score"], 3.0)
        self.assertEqual(res["max_score"], 3.0)
        self.assertEqual(res["percentage"], 100.0)
        self.assertEqual(len(res["steps"]), 3)
