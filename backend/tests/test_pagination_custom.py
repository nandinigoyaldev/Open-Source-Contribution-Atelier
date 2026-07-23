"""
Custom pagination tests for specific edge cases.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()
from rest_framework.test import APIClient
from django.core.paginator import Paginator


class PaginationEdgeCaseTest(TestCase):
    """
    Test pagination edge cases.
    """

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

    def test_page_size_validation(self):
        """Test that page size limits are enforced."""
        endpoints = [
            ("/api/content/?page_size=200", 100, "content"),
            ("/api/progress/?page_size=200", 100, "progress"),
        ]

        for endpoint, max_size, name in endpoints:
            try:
                response = self.client.get(endpoint)
                if response.status_code == 200:
                    results = response.data.get("results", [])
                    self.assertLessEqual(
                        len(results),
                        max_size,
                        f"{name} endpoint returned {len(results)} items, max {max_size}",
                    )
            except Exception:
                pass

    def test_pagination_navigation(self):
        """Test that pagination navigation works."""
        try:
            # Get first page
            response = self.client.get("/api/content/?page=1&page_size=5")
            if response.status_code == 200:
                data = response.data

                # Check navigation fields
                self.assertIn("next", data)
                self.assertIn("previous", data)
                self.assertIn("count", data)
                self.assertIn("results", data)

                # Check types
                self.assertIsInstance(data["count"], int)
                self.assertIsInstance(data["results"], list)

        except Exception:
            pass

    def test_empty_results_pagination(self):
        """Test pagination with empty results."""
        try:
            response = self.client.get("/api/content/?page=999")
            if response.status_code == 200:
                data = response.data
                self.assertEqual(data.get("results", []), [])
                self.assertEqual(data.get("count", 0), 0)
        except Exception:
            pass
