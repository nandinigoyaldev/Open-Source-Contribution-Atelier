import unittest

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from apps.challenges.models import Challenge
from apps.content.models import Lesson
from apps.dashboard.models import Issue
from apps.search.models import SearchDocument
from apps.search.tasks import index_model_for_search, remove_model_from_search
from apps.search.views import UnifiedSearchView

User = get_user_model()


def _is_postgres():
    vendor = settings.DATABASES["default"].get("ENGINE", "")
    return "postgresql" in vendor or "postgis" in vendor


class SearchEngineEdgeCaseTests(TestCase):
    def setUp(self):
        if not _is_postgres():
            raise unittest.SkipTest("PostgreSQL-only test")
        # Create test models
        self.user = User.objects.create_user(
            username="searchtestuser", email="test@search.com"
        )
        self.lesson1 = Lesson.objects.create(
            difficulty="Beginner",
            title="Introduction to React",
            slug="intro-to-react",
            summary="A comprehensive guide to React hooks.",
            content="Use useState and useEffect for side effects.",
        )
        self.lesson2 = Lesson.objects.create(
            difficulty="Advanced",
            title="Advanced Python Programming",
            slug="advanced-python",
            summary="Deep dive into Python internals.",
            content="Understanding the GIL, metaclasses, and memory management.",
        )
        self.challenge1 = Challenge.objects.create(
            title="Fix Navbar Bug",
            slug="fix-navbar",
            summary="The navbar is broken on mobile.",
            difficulty="Beginner",
            points=10,
        )
        self.issue1 = Issue.objects.create(
            title="Database Connection Pool",
            description="Optimize the connection pool for Postgres.",
            status="open",
            points=50,
        )

        # Manually index them
        self._index_model(self.user, self.user.username, self.user.email)
        self._index_model(
            self.lesson1,
            self.lesson1.title,
            f"{self.lesson1.summary} {self.lesson1.content}",
        )
        self._index_model(
            self.lesson2,
            self.lesson2.title,
            f"{self.lesson2.summary} {self.lesson2.content}",
        )
        self._index_model(
            self.challenge1, self.challenge1.title, self.challenge1.summary
        )
        self._index_model(self.issue1, self.issue1.title, self.issue1.description)
        self.factory = RequestFactory()
        self.view = UnifiedSearchView.as_view()

    def _index_model(self, obj, title, body):
        index_model_for_search(
            app_label=obj._meta.app_label,
            model_name=obj._meta.model_name,
            object_id=obj.pk,
            title=title,
            body_text=body,
        )

    def test_empty_query(self):
        """Edge Case: Query is completely empty."""
        request = self.factory.get("/api/search/", {"q": ""})
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

    def test_special_characters(self):
        """Edge Case: Query contains special SQL or regex characters."""
        request = self.factory.get("/api/search/", {"q": "%_**&&\\"})
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        # Should cleanly return empty, not throw syntax error
        self.assertEqual(len(response.data), 0)

    def test_typo_tolerance_trigram(self):
        """Custom Case: User types 'Pethon' instead of 'Python'."""
        request = self.factory.get("/api/search/", {"q": "Pethon"})
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        # Should still find the "Advanced Python Programming" lesson!
        self.assertGreater(len(response.data), 0)
        self.assertEqual(response.data[0]["title"], "Advanced Python Programming")

    def test_exact_full_text_search(self):
        """Custom Case: Standard Full-Text Search exact matching."""
        request = self.factory.get("/api/search/", {"q": "React"})
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["title"], "Introduction to React")

    def test_polymorphic_serializer_response(self):
        """Ensure the response formats the URL appropriately for different models."""
        request = self.factory.get("/api/search/", {"q": "searchtestuser"})
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        data = response.data[0]
        self.assertEqual(data["type"], "User")
        self.assertTrue(data["url"].startswith("/api/users/"))

        # Test Challenge URL
        request = self.factory.get("/api/search/", {"q": "Navbar"})
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["type"], "Challenge")
        self.assertTrue(response.data[0]["url"].startswith("/api/challenges/"))

        # Test Issue URL
        request = self.factory.get("/api/search/", {"q": "Database"})
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["type"], "Issue")
        self.assertTrue(response.data[0]["url"].startswith("/api/dashboard/issues/"))

    def test_stop_words_only(self):
        """Edge Case: Query contains only stop words (e.g., 'the', 'and', 'a')."""
        request = self.factory.get("/api/search/", {"q": "the and a with"})
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        # Stop words are ignored by Postgres FTS, so it should cleanly return empty or broad results depending on Trigram fallback
        # In our case, trigram might score low, so we just ensure it doesn't crash
        self.assertIsInstance(response.data, list)

    def test_case_insensitivity(self):
        """Edge Case: Ensure FTS and Trigram are case-insensitive."""
        request = self.factory.get("/api/search/", {"q": "rEaCt"})
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.data), 0)
        self.assertEqual(response.data[0]["title"], "Introduction to React")

    def test_non_existent_term(self):
        """Edge Case: Searching for a complete gibberish string."""
        request = self.factory.get("/api/search/", {"q": "asdfqwerzxcv"})
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

    def test_html_tags_in_query(self):
        """Edge Case: Searching with HTML tags should not break or cause 500s."""
        request = self.factory.get("/api/search/", {"q": "<html>React</html>"})
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        # Even with HTML tags, Postgres FTS strips symbols, so "React" might match
        self.assertIsInstance(response.data, list)
