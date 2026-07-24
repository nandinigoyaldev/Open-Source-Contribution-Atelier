import unittest
from unittest.mock import patch

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


class SearchCachingTests(TestCase):
    def setUp(self):
        from apps.search.tests import _is_postgres
        import unittest

        if not _is_postgres():
            raise unittest.SkipTest("PostgreSQL-only test")

        from django.core.cache import cache

        self.factory = RequestFactory()
        self.view = UnifiedSearchView.as_view()
        cache.clear()

    def test_search_results_are_cached(self):
        from django.core.cache import cache

        request = self.factory.get("/api/search/", {"q": "React"})

        # First call caches it
        response1 = self.view(request)
        self.assertEqual(response1.status_code, 200)

        version = cache.get("search_api_version", 1)
        cache_key = f"search_api:v{version}:q:React"

        # Verify it is in cache
        cached_data = cache.get(cache_key)
        self.assertIsNotNone(cached_data)

    def test_cache_version_bump(self):
        from django.core.cache import cache
        from apps.search.utils import bump_search_cache_version

        request = self.factory.get("/api/search/", {"q": "React"})
        self.view(request)

        version1 = cache.get("search_api_version", 1)

        # Simulating a model save
        bump_search_cache_version()

        version2 = cache.get("search_api_version", 1)
        self.assertEqual(version2, version1 + 1)


class MeilisearchIntegrationTests(TestCase):
    def setUp(self):
        from unittest.mock import MagicMock

        self.factory = RequestFactory()
        self.view = UnifiedSearchView.as_view()

    @patch("apps.search.tasks.get_meili_index")
    def test_tasks_sync_to_meilisearch(self, mock_get_index):
        from unittest.mock import MagicMock

        mock_index = MagicMock()
        mock_get_index.return_value = mock_index

        index_model_for_search(
            app_label="content",
            model_name="lesson",
            object_id=999,
            title="Meili Testing",
            body_text="Testing meili integration",
        )

        mock_index.add_documents.assert_called_once()
        args, _ = mock_index.add_documents.call_args
        self.assertEqual(args[0][0]["title"], "Meili Testing")

    @patch("apps.search.tasks.get_meili_index")
    def test_tasks_deindex_from_meilisearch(self, mock_get_index):
        from unittest.mock import MagicMock

        mock_index = MagicMock()
        mock_get_index.return_value = mock_index

        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(SearchDocument)
        doc = SearchDocument.objects.create(
            content_type=content_type,
            object_id=999,
            title="Meili Deindex",
            body_text="Testing deindex",
        )

        remove_model_from_search(
            app_label=content_type.app_label,
            model_name=content_type.model,
            object_id=999,
        )

        mock_index.delete_document.assert_called_once_with(str(doc.id))

    @patch("apps.search.views.get_meili_index")
    def test_view_queries_meilisearch_successfully(self, mock_get_index):
        from unittest.mock import MagicMock

        mock_index = MagicMock()
        mock_get_index.return_value = mock_index

        mock_index.search.return_value = {
            "hits": [
                {
                    "id": "1",
                    "title": "Meili Title",
                    "description": "Meili Desc",
                    "body_text": "Meili Body",
                    "content_type_name": "lesson",
                    "_formatted": {
                        "title": "Meili <mark>Title</mark>",
                        "description": "Meili Desc",
                        "body_text": "Meili Body",
                    },
                }
            ]
        }

        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(SearchDocument)
        SearchDocument.objects.create(
            id=1,
            content_type=content_type,
            object_id=1,
            title="Meili Title",
            body_text="Meili Body",
            content_type_name="lesson",
        )

        request = self.factory.get("/api/search/", {"q": "Title"})
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        results = response.data["results"] if isinstance(response.data, dict) else response.data
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Meili Title")
        self.assertEqual(
            results[0]["highlighted_title"], "Meili <mark>Title</mark>"
        )

    @patch("apps.search.views.get_meili_index")
    def test_view_postgres_fallback_on_meili_error(self, mock_get_index):
        from unittest.mock import MagicMock

        mock_index = MagicMock()
        mock_index.search.side_effect = Exception("Meili connection error")
        mock_get_index.return_value = mock_index

        if not _is_postgres():
            self.skipTest("Requires PostgreSQL")

        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(SearchDocument)

        # Let's index using the helper so the search vector is computed
        index_model_for_search(
            app_label=content_type.app_label,
            model_name=content_type.model,
            object_id=222,
            title="React Fallback",
            body_text="Testing FTS Fallback",
        )

        request = self.factory.get("/api/search/", {"q": "React"})
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.data), 0)
        self.assertEqual(response.data[0]["title"], "React Fallback")


class SearchFilterInjectionSecurityTests(TestCase):
    """Test security sanitization and validation against Meilisearch filter injection."""

    def setUp(self):
        self.factory = RequestFactory()
        self.view = UnifiedSearchView.as_view()

    def test_valid_content_type_filter_allowed(self):
        """Valid alphanumeric content type names should be allowed."""
        request = self.factory.get("/api/search/", {"q": "test", "type": "lesson"})
        response = self.view(request)
        self.assertEqual(response.status_code, 200)

    def test_injection_single_quote_rejected(self):
        """Injection attempt with single quote and OR condition must return 400."""
        request = self.factory.get(
            "/api/search/",
            {"q": "git", "content_type_filter": "Lesson' OR id > 0"},
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        errors = response.data.get("errors", response.data)
        self.assertIn("type", errors)

    def test_injection_semicolon_and_operators_rejected(self):
        """Injection attempt with semicolons or operators must return 400."""
        request = self.factory.get(
            "/api/search/",
            {"q": "git", "type": "lesson; DROP TABLE"},
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 400)

    def test_injection_special_chars_rejected(self):
        """Injection attempt with double quotes or parentheses must return 400."""
        invalid_inputs = [
            'lesson" OR 1=1',
            "lesson(1)",
            "lesson AND true",
            "lesson=1",
            "lesson > 0",
        ]
        for invalid in invalid_inputs:
            with self.subTest(invalid=invalid):
                request = self.factory.get("/api/search/", {"q": "git", "type": invalid})
                response = self.view(request)
                self.assertEqual(response.status_code, 400)

    @patch("apps.search.views.get_meili_index")
    def test_meilisearch_receives_sanitized_filter(self, mock_get_index):
        """Verify Meilisearch search options receive properly validated content_type_name filter."""
        from unittest.mock import MagicMock

        mock_index = MagicMock()
        mock_index.search.return_value = {"hits": []}
        mock_get_index.return_value = mock_index

        request = self.factory.get(
            "/api/search/", {"q": "git", "type": "challenge"}
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        mock_index.search.assert_called_once()
        _, kwargs = mock_index.search.call_args
        opts = kwargs if kwargs else _[1]
        self.assertEqual(opts["filter"], ["content_type_name = 'challenge'"])

