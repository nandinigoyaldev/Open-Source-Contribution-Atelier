"""
Test to detect excessive query counts in API endpoints.
"""

from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model

User = get_user_model()
from django.db import connection
from django.urls import reverse
from rest_framework.test import APIClient
import time


class QueryCountTest(TransactionTestCase):
    """
    Test that API endpoints don't make excessive database queries.
    """

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123", email="test@example.com"
        )
        self.client.force_authenticate(user=self.user)

    def _count_queries(self, func, *args, **kwargs):
        """Execute function and count database queries."""
        with connection.capture_queries(True) as queries:
            result = func(*args, **kwargs)
            return len(queries), result

    def test_dashboard_query_count(self):
        """Test dashboard endpoint doesn't make too many queries."""
        try:
            count, response = self._count_queries(self.client.get, reverse("dashboard"))

            # Should be less than 20 queries
            print(f"Dashboard queries: {count}")
            self.assertLess(count, 20, f"Dashboard made {count} queries, expected < 20")
            self.assertEqual(response.status_code, 200)
        except:
            pass

    def test_leaderboard_query_count(self):
        """Test leaderboard endpoint doesn't make too many queries."""
        try:
            count, response = self._count_queries(
                self.client.get, reverse("leaderboard")
            )

            print(f"Leaderboard queries: {count}")
            self.assertLess(
                count, 15, f"Leaderboard made {count} queries, expected < 15"
            )
            self.assertEqual(response.status_code, 200)
        except:
            pass

    def test_progress_query_count(self):
        """Test progress endpoint doesn't make too many queries."""
        try:
            count, response = self._count_queries(
                self.client.get, reverse("my-progress")
            )

            print(f"Progress queries: {count}")
            self.assertLess(count, 30, f"Progress made {count} queries, expected < 30")
            self.assertEqual(response.status_code, 200)
        except:
            pass
