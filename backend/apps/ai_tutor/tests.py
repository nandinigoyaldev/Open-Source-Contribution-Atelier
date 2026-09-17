from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.ai_tutor.services import AiTutorService
from apps.content.models import Lesson

User = get_user_model()


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_BROKER_URL="memory://")
class AiTutorTests(TestCase):
    def setUp(self):
        self.patcher = patch("apps.core.cache.signals.invalidate_tag_task")
        self.mock_invalidate = self.patcher.start()
        self.addCleanup(self.patcher.stop)

        self.client = APIClient()
        self.user = User.objects.create_user(
            username="tutortestuser",
            email="tutor@test.com",
            password="password123",
        )
        self.client.force_authenticate(user=self.user)

        self.lesson = Lesson.objects.create(
            title="Git Basics",
            slug="git-basics",
            summary="Learn the fundamentals of Git version control.",
            content="Git is a distributed version control system...",
            difficulty="Beginner",
        )

    def test_ask_view_unauthenticated(self):
        self.client.logout()
        response = self.client.post("/api/ai/tutor/ask/", {"question": "What is git?"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_ask_view_missing_question(self):
        response = self.client.post("/api/ai/tutor/ask/", {"question": "   "})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_fallback_git_response(self):
        response = self.client.post(
            "/api/ai/tutor/ask/",
            {"question": "How does git work?", "lesson_slug": self.lesson.slug},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "text/event-stream")
        content = b"".join(response.streaming_content).decode("utf-8")
        self.assertIn("version", content.lower())
        self.assertIn("control", content.lower())

    def test_fallback_commit_response(self):
        answer = AiTutorService.get_response(question="What is a commit?")
        self.assertIn("snapshot", answer.lower())

    def test_socratic_progressive_hints(self):
        hint1 = AiTutorService.get_hint(hint_level=1, topic_or_exercise="git branches")
        hint2 = AiTutorService.get_hint(hint_level=2, topic_or_exercise="git branches")
        self.assertIn("Hint 1", hint1)
        self.assertIn("Hint 2", hint2)

    def test_evaluate_correct_attempt(self):
        eval_result = AiTutorService.evaluate_attempt(
            user_input="git switch -c feat/add-login",
            expected_concept_or_command="git switch -c feat/add-login",
        )
        self.assertTrue(eval_result["is_correct"])
        self.assertIn("Excellent", eval_result["feedback"])

    def test_evaluate_mistake_confusing_fork_with_clone(self):
        eval_result = AiTutorService.evaluate_attempt(
            user_input="git clone https://github.com/upstream/repo.git",
            expected_concept_or_command="fork repository on GitHub",
        )
        self.assertFalse(eval_result["is_correct"])
        self.assertEqual(
            eval_result["mistake_detected"], "Confused local clone with GitHub fork"
        )
        self.assertTrue(len(eval_result["hint"]) > 0)

    def test_evaluate_endpoint_view(self):
        response = self.client.post(
            "/api/ai/tutor/evaluate/",
            {
                "user_input": "git commit",
                "expected": "git commit -m 'feat: add button'",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_correct"])
        self.assertIn("commit message", response.data["feedback"].lower())

    def test_llm_response_mocked(self):
        mock_openai = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = (
            "Git commits track your repository changes over time."
        )
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_openai.chat.completions.create.return_value = mock_response

        with self.settings(OPENAI_API_KEY="sk-fake-key-for-test"):
            with patch.dict("sys.modules", {"openai": mock_openai}):
                answer = AiTutorService.get_response(
                    question="Explain commits",
                    lesson_context="Lesson title: Git Basics",
                    history=[{"question": "Hi", "answer": "Hello!"}],
                )

                self.assertEqual(
                    answer, "Git commits track your repository changes over time."
                )
                mock_openai.chat.completions.create.assert_called_once()
