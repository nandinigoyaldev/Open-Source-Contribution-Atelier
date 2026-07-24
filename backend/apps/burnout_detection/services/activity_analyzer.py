"""
Analyze contributor activity patterns.
"""

import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List
from django.contrib.auth import get_user_model

User = get_user_model()
from django.conf import settings
from apps.burnout_detection.models import ContributorActivity
import logging

logger = logging.getLogger(__name__)


class ActivityAnalyzer:
    """
    Analyze GitHub activity patterns.
    """

    def __init__(self):
        self.token = getattr(settings, "GITHUB_TOKEN", None)
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }
        self.base_url = "https://api.github.com"

    def analyze_user(self, user: User, github_username: str) -> Dict[str, Any]:
        """
        Analyze GitHub activity for a user.
        """
        # Fetch user data
        user_data = self._fetch_user(github_username)
        events = self._fetch_events(github_username)

        # Calculate metrics
        commits = self._count_commits(events)
        reviews = self._count_reviews(events)
        comments = self._count_comments(events)

        # Calculate trends
        activity_trend = self._calculate_trend(events, "commit")
        review_trend = self._calculate_trend(events, "review")

        # Calculate response times
        avg_response_time = self._calculate_response_time(events)

        return {
            "commits_last_week": commits["week"],
            "commits_last_month": commits["month"],
            "reviews_last_week": reviews["week"],
            "reviews_last_month": reviews["month"],
            "comments_last_week": comments["week"],
            "comments_last_month": comments["month"],
            "avg_response_time": avg_response_time,
            "activity_trend": activity_trend,
            "review_trend": review_trend,
        }

    def _fetch_user(self, username: str) -> Dict:
        """Fetch user data."""
        response = requests.get(
            f"{self.base_url}/users/{username}", headers=self.headers
        )
        return response.json() if response.status_code == 200 else {}

    def _fetch_events(self, username: str) -> List[Dict]:
        """Fetch user events."""
        response = requests.get(
            f"{self.base_url}/users/{username}/events", headers=self.headers
        )
        return response.json() if response.status_code == 200 else []

    def _count_commits(self, events: List[Dict]) -> Dict[str, int]:
        """Count commits in last week and month."""
        now = datetime.now()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        week_count = 0
        month_count = 0

        for event in events:
            if event.get("type") == "PushEvent":
                created_at = datetime.fromisoformat(
                    event.get("created_at", "").replace("Z", "+00:00")
                )
                if created_at >= week_ago:
                    week_count += 1
                if created_at >= month_ago:
                    month_count += 1

        return {"week": week_count, "month": month_count}

    def _count_reviews(self, events: List[Dict]) -> Dict[str, int]:
        """Count reviews in last week and month."""
        now = datetime.now()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        week_count = 0
        month_count = 0

        for event in events:
            if event.get("type") == "PullRequestReviewEvent":
                created_at = datetime.fromisoformat(
                    event.get("created_at", "").replace("Z", "+00:00")
                )
                if created_at >= week_ago:
                    week_count += 1
                if created_at >= month_ago:
                    month_count += 1

        return {"week": week_count, "month": month_count}

    def _count_comments(self, events: List[Dict]) -> Dict[str, int]:
        """Count comments in last week and month."""
        now = datetime.now()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        week_count = 0
        month_count = 0

        for event in events:
            if event.get("type") in [
                "IssueCommentEvent",
                "PullRequestReviewCommentEvent",
            ]:
                created_at = datetime.fromisoformat(
                    event.get("created_at", "").replace("Z", "+00:00")
                )
                if created_at >= week_ago:
                    week_count += 1
                if created_at >= month_ago:
                    month_count += 1

        return {"week": week_count, "month": month_count}

    def _calculate_trend(self, events: List[Dict], event_type: str) -> float:
        """Calculate activity trend."""
        # Simplified: compare last 2 weeks vs previous 2 weeks
        now = datetime.now()
        recent_start = now - timedelta(days=14)
        previous_start = now - timedelta(days=28)

        recent_count = 0
        previous_count = 0

        for event in events:
            created_at = datetime.fromisoformat(
                event.get("created_at", "").replace("Z", "+00:00")
            )
            if created_at >= recent_start:
                recent_count += 1
            elif created_at >= previous_start:
                previous_count += 1

        if previous_count == 0:
            return 1.0 if recent_count > 0 else 0.0

        return (recent_count - previous_count) / previous_count

    def _calculate_response_time(self, events: List[Dict]) -> float:
        """Calculate average response time."""
        # Simplified: count PR review responses
        response_times = []

        for event in events:
            if event.get("type") == "PullRequestReviewEvent":
                # Simplified calculation
                response_times.append(2.0)  # Placeholder

        if response_times:
            return sum(response_times) / len(response_times)
        return 0.0
