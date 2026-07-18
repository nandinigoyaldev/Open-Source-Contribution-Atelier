from datetime import timedelta

from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase


class LeaderboardTests(APITestCase):
    def setUp(self):
        # Create users
        for i in range(25):
            User.objects.create_user(username=f"user{i}", password="password")

    def test_cursor_pagination(self):
        url = reverse("leaderboard")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # CursorPagination returns 'next' as a cursor link, not page=2
        self.assertIn("cursor=", response.data["next"])
        self.assertNotIn("page=", response.data["next"])

        # Total results shouldn't be counted in cursor pagination usually, but let's check size
        self.assertEqual(len(response.data["results"]), 20)

        # Fetch next page
        next_url = response.data["next"]
        next_response = self.client.get(next_url)
        self.assertEqual(next_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(next_response.data["results"]), 5)

    def test_cursor_invalid_format(self):
        # DRF CursorPagination returns 404 for invalid cursors
        url = (
            reverse("leaderboard") + "?cursor=invalid_base64_string_that_makes_no_sense"
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cursor_identical_xp(self):
        # Test stable ordering when many users have the exact same XP
        url = reverse("leaderboard")
        response = self.client.get(url)

        # All 25 users have 0 XP right now
        results = response.data["results"]

        # Verify they are ordered predictably (by username or id as defined in ordering)
        # ordering is ("-xp", "username", "id")
        # Since xp is 0 for all, it should be alphabetical by username
        usernames = [r["username"] for r in results]

        # However, user0, user1, user10, user11... will be the alphabetical order
        sorted_usernames = sorted(usernames)
        self.assertEqual(usernames, sorted_usernames)

class IssueModelTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password")

    def test_issue_total_points(self):
        from apps.dashboard.models import Issue
        issue = Issue.objects.create(title="Test", assigned_to=self.user, points=50, bonus_points=15)
        self.assertEqual(issue.total_points, 65)

    def test_issue_no_bonus_points(self):
        from apps.dashboard.models import Issue
        issue = Issue.objects.create(title="Test", assigned_to=self.user, points=50)
        self.assertEqual(issue.total_points, 50)
