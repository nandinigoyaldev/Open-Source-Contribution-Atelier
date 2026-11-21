"""
Test to detect excessive query counts in API endpoints.
"""

import time
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework.test import APIClient

User = get_user_model()


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
        """Test dashboard contributor endpoint doesn't make too many queries."""
        endpoint = reverse("dashboard:contributor_stats")
        count, response = self._count_queries(self.client.get, endpoint)

        self.assertEqual(
            response.status_code,
            200,
            f"Expected 200 from endpoint '{endpoint}', got {response.status_code}",
        )
        self.assertLessEqual(
            count,
            25,
            f"Endpoint '{endpoint}' exceeded query budget: executed {count} queries, expected <= 25",
        )

    def test_leaderboard_query_count(self):
        """Test leaderboard endpoint doesn't make too many queries."""
        endpoint = reverse("leaderboard")
        count, response = self._count_queries(self.client.get, endpoint)

        self.assertEqual(
            response.status_code,
            200,
            f"Expected 200 from endpoint '{endpoint}', got {response.status_code}",
        )
        self.assertLessEqual(
            count,
            15,
            f"Endpoint '{endpoint}' exceeded query budget: executed {count} queries, expected <= 15",
        )

    def test_progress_query_count(self):
        """Test progress endpoint doesn't make too many queries."""
        try:
            endpoint = reverse("progress:my-progress")
        except Exception:
            endpoint = "/api/progress/my-progress/"

        count, response = self._count_queries(self.client.get, endpoint)
        if response.status_code == 200:
            self.assertLessEqual(
                count,
                30,
                f"Endpoint '{endpoint}' exceeded query budget: executed {count} queries, expected <= 30",
            )
