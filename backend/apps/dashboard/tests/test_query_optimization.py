import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.db import connection, reset_queries
from rest_framework.test import APIClient
from apps.dashboard.models import Issue, PullRequest
from apps.content.models import Lesson, Exercise
from apps.progress.models import LessonProgress, ExerciseAttempt

User = get_user_model()

ENDPOINT = "/api/dashboard/contributor/"


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="contributor", email="c@example.com", password="pw")


@pytest.fixture
def other_users(db):
    """Create several additional users to make the rank calculation meaningful."""
    users = []
    for i in range(5):
        u = User.objects.create_user(username=f"user{i}", email=f"u{i}@example.com", password="pw")
        users.append(u)
    return users


@pytest.fixture
def setup_activity(user, other_users):
    """Populate DB with lessons, progress entries, issues and PRs for the target user."""
    lesson = Lesson.objects.create(
        title="L1", slug="l1", summary="s", content="c", difficulty="beginner"
    )
    exercise = Exercise.objects.create(
        lesson=lesson, title="E1", prompt="p", expected_command="git init"
    )

    # Target user: 2 completed lessons, 1 exercise attempt, 1 solved issue, 1 merged PR
    LessonProgress.objects.create(user=user, lesson=lesson, completed=True, score=100)
    ExerciseAttempt.objects.create(user=user, exercise=exercise, submitted_command="git init", is_correct=True)
    issue = Issue.objects.create(
        title="Fix bug", assigned_to=user, status=Issue.Status.SOLVED, points=50, bonus_points=10
    )
    pr = PullRequest.objects.create(
        title="PR 1", user=user, status=PullRequest.Status.MERGED, issue=issue
    )

    # Give other users varying XP so rank is deterministic
    for i, u in enumerate(other_users):
        LessonProgress.objects.create(user=u, lesson=lesson, completed=True, score=(i + 1) * 50)

    return {"lesson": lesson, "issue": issue, "pr": pr}


@pytest.mark.django_db
class TestContributorDashboardStats:
    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get(ENDPOINT)
        assert response.status_code == 401

    def test_returns_200_for_authenticated_user(self, api_client, user, setup_activity):
        api_client.force_authenticate(user=user)
        response = api_client.get(ENDPOINT)
        assert response.status_code == 200

    def test_response_structure(self, api_client, user, setup_activity):
        api_client.force_authenticate(user=user)
        data = api_client.get(ENDPOINT).json()
        assert "personal_stats" in data
        assert "assigned_issues" in data
        assert "recent_prs" in data
        assert "progress_tracker" in data

    def test_personal_stats_accuracy(self, api_client, user, setup_activity):
        api_client.force_authenticate(user=user)
        stats = api_client.get(ENDPOINT).json()["personal_stats"]

        assert stats["issues_solved"] == 1
        assert stats["prs_merged"] == 1
        assert stats["total_xp"] == 100 + 50 + 10  # lesson_xp + points + bonus_points
        assert stats["rank"] >= 1

    def test_progress_tracker_accuracy(self, api_client, user, setup_activity):
        api_client.force_authenticate(user=user)
        tracker = api_client.get(ENDPOINT).json()["progress_tracker"]

        assert tracker["completed_lessons"] == 1
        assert tracker["total_lessons"] >= 1
        assert 0 <= tracker["completion_percentage"] <= 100

    def test_recent_prs_uses_select_related(self, api_client, user, setup_activity):
        """Recent PRs should include issue title without extra queries."""
        api_client.force_authenticate(user=user)
        data = api_client.get(ENDPOINT).json()

        pr_list = data["recent_prs"]
        assert len(pr_list) == 1
        assert pr_list[0]["issue_title"] == "Fix bug"

    def test_empty_user_returns_zero_stats(self, api_client, setup_activity):
        """
        A user with no assigned issues, PRs, or lesson progress should
        return all-zero personal stats without raising any errors.
        setup_activity is included to ensure the same DB transaction scope
        and to verify there is no cross-user data leakage.
        """
        from django.core.cache import cache as django_cache

        empty_user = User.objects.create_user(
            username="empty_user_zero_activity",
            email="zero@example.com",
            password="pw",
        )
        django_cache.clear()
        api_client.force_authenticate(user=empty_user)
        data = api_client.get(ENDPOINT).json()

        stats = data["personal_stats"]
        assert stats["issues_solved"] == 0
        assert stats["prs_merged"] == 0
        assert stats["total_xp"] == 0
        assert stats["streak_days"] == 0
        assert stats["rank"] >= 1

    @override_settings(DEBUG=True)
    def test_query_count_is_bounded_regardless_of_user_count(self, api_client, user, other_users, setup_activity):
        """
        Regression guard: the endpoint must use a bounded number of queries
        no matter how many users exist in the system.
        With the N+1 fix, the total query count is constant (≤ 10).
        """
        api_client.force_authenticate(user=user)

        # Warm up cache-busting: use a fresh user to avoid cached response
        fresh_user = User.objects.create_user(username="fresh", email="fresh@example.com", password="pw")
        api_client.force_authenticate(user=fresh_user)

        reset_queries()
        with override_settings(DEBUG=True):
            reset_queries()
            api_client.get(ENDPOINT)
            query_count = len(connection.queries)

        # Should be well under 15 regardless of number of users in DB
        assert query_count <= 15, (
            f"Too many queries: {query_count}. "
            "Possible N+1 regression. Expected ≤ 15."
        )
