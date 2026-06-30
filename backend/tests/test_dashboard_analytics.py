import pytest
from apps.content.models import Lesson
from apps.dashboard.models import Issue, PullRequest
from apps.progress.models import LessonProgress
from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def clear_caches_each_test():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
def test_anonymous_access_denied():
    client = APIClient()

    # Admin endpoint requires authentication
    admin_response = client.get("/api/dashboard/admin/")
    assert admin_response.status_code == 401

    # Contributor endpoint requires authentication
    contributor_response = client.get("/api/dashboard/contributor/")
    assert contributor_response.status_code == 401


@pytest.mark.django_db
def test_contributor_role_enforcement():
    # Regular contributor user
    contributor = User.objects.create_user(
        username="contrib1",
        email="contrib1@example.com",
        password="password123",
        is_staff=False,
    )

    client = APIClient()
    client.force_authenticate(user=contributor)

    # Contributor gets 403 Forbidden for admin dashboard
    admin_response = client.get("/api/dashboard/admin/")
    assert admin_response.status_code == 403

    # Contributor gets 200 OK for contributor dashboard
    contributor_response = client.get("/api/dashboard/contributor/")
    assert contributor_response.status_code == 200


@pytest.mark.django_db
def test_admin_access_allowed():
    # Admin user
    admin = User.objects.create_user(
        username="admin1",
        email="admin1@example.com",
        password="password123",
        is_staff=True,
    )

    client = APIClient()
    client.force_authenticate(user=admin)

    # Admin gets 200 OK for admin dashboard
    admin_response = client.get("/api/dashboard/admin/")
    assert admin_response.status_code == 200

    # Admin gets 200 OK for contributor dashboard (accessing their own stats)
    contributor_response = client.get("/api/dashboard/contributor/")
    assert contributor_response.status_code == 200


@pytest.mark.django_db
def test_admin_dashboard_statistics():
    admin = User.objects.create_user(username="admin", is_staff=True)
    contrib = User.objects.create_user(username="contrib", is_staff=False)

    # Create mock issues
    issue1 = Issue.objects.create(
        title="Issue 1",
        description="desc",
        status=Issue.Status.SOLVED,
        points=100,
        assigned_to=contrib,
    )
    issue2 = Issue.objects.create(
        title="Issue 2", description="desc", status=Issue.Status.OPEN, points=50
    )

    # Create mock PRs
    pr1 = PullRequest.objects.create(
        title="PR 1", status=PullRequest.Status.MERGED, issue=issue1, user=contrib
    )
    pr2 = PullRequest.objects.create(
        title="PR 2", status=PullRequest.Status.OPEN, issue=issue2, user=contrib
    )

    # Create mock lesson progress
    lesson = Lesson.objects.create(
        title="Git Basics",
        slug="git-basics",
        summary="basics",
        content="content",
        order=1,
    )
    LessonProgress.objects.create(
        user=contrib, lesson=lesson, completed=True, score=200
    )

    client = APIClient()
    client.force_authenticate(user=admin)

    response = client.get("/api/dashboard/admin/")
    assert response.status_code == 200

    stats = response.data["system_stats"]
    assert stats["total_issues"] == 2
    assert stats["solved_issues"] == 1
    assert stats["open_issues"] == 1
    assert stats["total_prs"] == 2
    assert stats["merged_prs"] == 1
    assert stats["pending_prs"] == 1
    assert stats["active_contributors"] == 1

    # Verify pending PRs list
    pending = response.data["pending_prs"]
    assert len(pending) == 1
    assert pending[0]["title"] == "PR 2"
    assert pending[0]["contributor"] == "contrib"
    assert pending[0]["issue_title"] == "Issue 2"


@pytest.mark.django_db
def test_leaderboard_is_paginated_to_twenty_contributors_per_page():
    lesson = Lesson.objects.create(
        title="Git Basics",
        slug="git-basics",
        summary="basics",
        content="content",
        order=1,
    )

    for index in range(25):
        contributor = User.objects.create_user(
            username=f"contrib{index:02d}",
            is_staff=False,
        )
        LessonProgress.objects.create(
            user=contributor,
            lesson=lesson,
            completed=True,
            score=index,
        )

    client = APIClient()

    first_page = client.get("/api/leaderboard/")
    assert first_page.status_code == 200
    assert first_page.data["count"] == 25
    assert len(first_page.data["results"]) == 20
    assert first_page.data["next"] is not None
    assert first_page.data["previous"] is None
    assert first_page.data["results"][0]["username"] == "contrib24"
    assert first_page.data["results"][0]["xp"] == 24

    second_page = client.get("/api/leaderboard/?page=2")
    assert second_page.status_code == 200
    assert len(second_page.data["results"]) == 5
    assert second_page.data["next"] is None
    assert second_page.data["previous"] is not None
    assert second_page.data["results"][0]["username"] == "contrib04"


@pytest.mark.django_db
def test_contributor_dashboard_statistics():
    contrib = User.objects.create_user(username="contrib", is_staff=False)

    # Create mock issues
    issue = Issue.objects.create(
        title="My Assigned Issue",
        description="desc",
        status=Issue.Status.IN_PROGRESS,
        points=100,
        assigned_to=contrib,
    )

    # Create mock PRs
    PullRequest.objects.create(
        title="PR Title", status=PullRequest.Status.OPEN, issue=issue, user=contrib
    )

    # Create mock lessons
    lesson = Lesson.objects.create(
        title="Git Basics",
        slug="git-basics",
        summary="basics",
        content="content",
        order=1,
    )
    LessonProgress.objects.create(
        user=contrib, lesson=lesson, completed=True, score=150
    )

    client = APIClient()
    client.force_authenticate(user=contrib)

    response = client.get("/api/dashboard/contributor/")
    assert response.status_code == 200

    # Personal stats assertions
    personal = response.data["personal_stats"]
    assert personal["issues_solved"] == 0
    assert personal["prs_merged"] == 0
    assert (
        personal["total_xp"] == 150
    )  # 150 score from completed lesson, 0 from unresolved issue

    # Assigned issues assertions
    assigned = response.data["assigned_issues"]
    assert len(assigned) == 1
    assert assigned[0]["title"] == "My Assigned Issue"
    assert assigned[0]["status"] == "in_progress"

    # Recent PRs assertions
    recent = response.data["recent_prs"]
    assert len(recent) == 1
    assert recent[0]["title"] == "PR Title"
    assert recent[0]["status"] == "open"

    # Progress tracker assertions
    tracker = response.data["progress_tracker"]
    assert tracker["completed_lessons"] == 1
    assert tracker["total_lessons"] == 1
    assert tracker["completion_percentage"] == 100


@pytest.mark.django_db
def test_caching_and_signal_invalidation():
    admin = User.objects.create_user(username="admin", is_staff=True)
    contrib = User.objects.create_user(username="contrib", is_staff=False)

    client = APIClient()
    client.force_authenticate(user=admin)

    # First request calculates stats and caches them
    response1 = client.get("/api/dashboard/admin/")
    assert response1.status_code == 200
    assert response1.data["system_stats"]["total_issues"] == 0

    # Manually add an issue to database (bypass django signals to simulate caching)
    # Actually django signals will fire here because we're calling Issue.objects.create,
    # so the cache will be invalidated. Let's verify that cache WAS cleared and stats updated!
    Issue.objects.create(
        title="Direct Issue", description="desc", status=Issue.Status.OPEN
    )

    # Second request should get the new data because signals invalidated the cache
    response2 = client.get("/api/dashboard/admin/")
    assert response2.status_code == 200
    assert response2.data["system_stats"]["total_issues"] == 1
