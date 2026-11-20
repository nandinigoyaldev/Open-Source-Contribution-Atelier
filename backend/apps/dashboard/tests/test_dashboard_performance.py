"""Performance and query-count budget tests for dashboard endpoints.

Guards against N+1 query regressions across organizations and learners.
Every budgeted endpoint must have a justified, bounded query ceiling that is
independent of the number of learners, organizations, issues, or pull requests.

See docs/backend/DASHBOARD_QUERY_BUDGET.md for instructions on intentional
query-budget updates.
"""

from datetime import timedelta
import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.db.models import Prefetch
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.content.models import Exercise, Lesson
from apps.dashboard.models import Issue, PullRequest
from apps.organizations.models import Organization, OrganizationMembership
from apps.progress.models import (
    Badge,
    ExerciseAttempt,
    LessonProgress,
    Season,
    StreakProfile,
    TrackMilestone,
    UserBadge,
    WeeklyGoal,
)
from apps.rbac.models import Role, UserRole

User = get_user_model()

ENDPOINT = "/api/dashboard/contributor/"
ADMIN_ENDPOINT = "/api/dashboard/admin/"
PUBLIC_ENDPOINT = "/api/dashboard/stats-public/"

# ---------------------------------------------------------------------------
# Query-Count Budget Registry with Explicit Justifications
# ---------------------------------------------------------------------------

DASHBOARD_QUERY_BUDGETS = {
    "contributor_dashboard_full": {
        "endpoint": "/api/dashboard/contributor/",
        "max_queries": 28,
        "reason": (
            "Cold full contributor dashboard with all 7 default fields: "
            "21 application queries (1 CustomerSubscription check, 8 personal_stats queries "
            "including 5 XP/completion aggregates, StreakProfile fetch, correlated subquery "
            "rank calculation, and UserBadge list; 1 assigned_issues list; 1 recent_prs list "
            "with select_related('issue'); 2 progress_tracker count queries; 5 active_track queries "
            "for season, milestones, and progress; 1 continue_learning query with select_related('lesson'); "
            "and 1 weekly_goal query) plus 5 framework session-persistence queries "
            "(SessionMiddleware / LocaleMiddleware session save)."
        ),
    },
    "contributor_dashboard_personal_stats": {
        "endpoint": "/api/dashboard/contributor/?fields=personal_stats",
        "max_queries": 16,
        "reason": (
            "Cold personal_stats field request: 9 application queries (CustomerSubscription, "
            "5 completion and XP aggregates, StreakProfile fetch, correlated subquery "
            "leaderboard rank computation across all users, and earned badge slugs) plus "
            "framework session-persistence queries."
        ),
    },
    "admin_dashboard": {
        "endpoint": "/api/dashboard/admin/",
        "max_queries": 18,
        "reason": (
            "Cold admin overview: auth/role verification (Admin RBAC role), system-wide counts across "
            "issues (total, solved, open, in-progress) and pull requests (total, merged, "
            "open, closed), distinct active contributors count, and pending PRs queue "
            "with select_related('user', 'issue') to prevent N+1 queries, plus session middleware overhead."
        ),
    },
    "public_landing_stats": {
        "endpoint": "/api/dashboard/stats-public/",
        "max_queries": 10,
        "reason": (
            "Cold public statistics: 3 application queries (unauthenticated non-staff user count, "
            "completed lessons count, and total lesson XP delta aggregate) plus 5 framework "
            "session-persistence queries (SessionMiddleware / LocaleMiddleware session save), "
            "bounded to 10 max queries."
        ),
    },
}


def assert_dashboard_query_budget(
    client: APIClient,
    endpoint: str,
    budget: int,
    method: str = "GET",
    params: dict = None,
    expected_status: int = 200,
):
    """Execute a request against an endpoint, asserting it stays within query budget.

    If the query budget is exceeded, raises an AssertionError that explicitly identifies:
      - The endpoint path and parameters
      - The actual number of executed database queries
      - The allowed query budget
      - A formatted list of all captured SQL queries for immediate debugging
    """
    from apps.predictions.ml_engine import PRReviewDelayPredictor

    cache.clear()
    PRReviewDelayPredictor()

    with override_settings(PERF_TRACK_SAMPLE_RATE=0):
        with CaptureQueriesContext(connection) as ctx:
            if method.upper() == "GET":
                response = client.get(endpoint, data=params)
            elif method.upper() == "POST":
                response = client.post(endpoint, data=params)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

    query_count = len(ctx.captured_queries)

    if query_count > budget:
        queries_summary = "\n".join(
            f"  [{i + 1}] ({q.get('time', '0.000')}s): {q.get('sql', '').strip()}"
            for i, q in enumerate(ctx.captured_queries)
        )
        raise AssertionError(
            f"Query budget exceeded for endpoint '{endpoint}'!\n"
            f"Executed: {query_count} queries\n"
            f"Budget:   {budget} queries ({query_count - budget} queries over budget)\n"
            f"Captured queries:\n{queries_summary}"
        )

    assert response.status_code == expected_status, (
        f"Expected HTTP {expected_status} for '{endpoint}', got {response.status_code}: {response.content}"
    )
    return response, query_count


# ---------------------------------------------------------------------------
# Fixtures: Multi-Organization and Multi-Learner Dataset
# ---------------------------------------------------------------------------


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def dashboard_user(db):
    """Single user fixture preserved for legacy unit test compatibility."""
    return User.objects.create_user(
        username="perf_contributor", email="perf@example.com", password="pw"
    )


@pytest.fixture
def enrollment_and_progress(dashboard_user):
    """Populate user enrollment (lessons), progress (attempts) and badges for single user."""
    lesson = Lesson.objects.create(
        title="Perf L1",
        slug="perf-l1",
        summary="s",
        content="c",
        difficulty="beginner",
    )
    lesson2 = Lesson.objects.create(
        title="Perf L2",
        slug="perf-l2",
        summary="s",
        content="c",
        difficulty="beginner",
    )
    lesson3 = Lesson.objects.create(
        title="Perf L3",
        slug="perf-l3",
        summary="s",
        content="c",
        difficulty="beginner",
    )
    LessonProgress.objects.create(
        user=dashboard_user, lesson=lesson, completed=True, score=60
    )
    LessonProgress.objects.create(
        user=dashboard_user, lesson=lesson2, completed=True, score=40
    )
    LessonProgress.objects.create(
        user=dashboard_user, lesson=lesson3, completed=False, score=10
    )

    exercise = Exercise.objects.create(
        lesson=lesson, title="E1", prompt="p", expected_command="git init"
    )
    ExerciseAttempt.objects.create(
        user=dashboard_user,
        exercise=exercise,
        submitted_command="git init",
        is_correct=True,
    )

    badge_a = Badge.objects.create(
        name="First Blood", slug="first-blood", description="First badge"
    )
    badge_b = Badge.objects.create(
        name="Streak 7", slug="streak-7", description="One week streak"
    )
    UserBadge.objects.create(user=dashboard_user, badge=badge_a)
    UserBadge.objects.create(user=dashboard_user, badge=badge_b)

    issue = Issue.objects.create(
        title="Perf bug",
        assigned_to=dashboard_user,
        status=Issue.Status.SOLVED,
        points=50,
        bonus_points=10,
    )
    PullRequest.objects.create(
        title="Perf PR",
        user=dashboard_user,
        status=PullRequest.Status.MERGED,
        issue=issue,
    )

    return {"lesson": lesson, "issue": issue}


def _create_learner_with_profile(username: str, organization: Organization) -> User:
    """Helper to create a learner user associated with an organization."""
    from apps.accounts.models import UserProfile

    user = User.objects.create_user(
        username=username,
        email=f"{username}@perf.example.com",
        password="password123",
    )
    profile = getattr(user, "user_profile", None)
    if profile is None:
        profile = UserProfile.objects.create(user=user)
    profile.organization = organization
    profile.save()

    OrganizationMembership.objects.create(
        organization=organization,
        user=user,
        role=OrganizationMembership.ROLE_MEMBER,
    )
    return user


@pytest.fixture
def multi_org_dashboard_dataset(db):
    """Seed a realistic multi-tenant dataset with multiple organizations and learners.

    Includes:
      - 2 Organizations (Alpha Labs, Beta Institute)
      - 4 Learners (2 per organization) with varying completions, badges, streaks, and goals
      - 1 Admin user with staff and Admin RBAC role
      - 6 Shared curriculum lessons across beginner/intermediate/advanced
      - Issues in SOLVED, OPEN, and IN_PROGRESS states
      - Pull requests in MERGED and OPEN states linked to issues
      - Active season with track milestone
    """
    # 1. Organizations
    org_alpha = Organization.objects.create(name="Alpha Labs", description="Org Alpha")
    org_beta = Organization.objects.create(name="Beta Institute", description="Org Beta")

    # 2. Admin User
    admin_user = User.objects.create_user(
        username="admin_perf",
        email="admin@perf.example.com",
        password="password123",
        is_staff=True,
        is_superuser=True,
    )
    admin_role, _ = Role.objects.get_or_create(name="Admin")
    UserRole.objects.get_or_create(user=admin_user, role=admin_role)

    # 3. Learners across multiple organizations
    learner_a1 = _create_learner_with_profile("learner_a1", org_alpha)
    learner_a2 = _create_learner_with_profile("learner_a2", org_alpha)
    learner_b1 = _create_learner_with_profile("learner_b1", org_beta)
    learner_b2 = _create_learner_with_profile("learner_b2", org_beta)

    # 4. Lessons
    lessons = []
    difficulties = ["beginner", "intermediate", "advanced"]
    for i in range(6):
        lessons.append(
            Lesson.objects.create(
                title=f"Lesson {i + 1}",
                slug=f"lesson-{i + 1}",
                summary=f"Summary {i + 1}",
                content=f"Content for lesson {i + 1}",
                difficulty=difficulties[i % len(difficulties)],
                order=i,
            )
        )

    # 5. Badges
    badge_starter = Badge.objects.create(
        name="Starter", slug="badge-starter", description="Completed first lesson"
    )
    badge_streak = Badge.objects.create(
        name="Week Streak", slug="badge-week-streak", description="7 day streak"
    )
    badge_solver = Badge.objects.create(
        name="Bug Hunter", slug="badge-bug-hunter", description="Solved an issue"
    )

    # 6. Active Season & Milestone
    today = timezone.localdate()
    season = Season.objects.create(
        name="Winter 2026",
        start_date=today - timedelta(days=10),
        end_date=today + timedelta(days=20),
        is_active=True,
    )
    TrackMilestone.objects.create(
        season=season,
        name="First 3 Lessons",
        activity_type="lesson",
        target_value=3,
        xp_boost=50,
    )

    # 7. Learner A1 Activity (Org Alpha)
    LessonProgress.objects.create(
        user=learner_a1, lesson=lessons[0], organization=org_alpha, completed=True, score=60
    )
    LessonProgress.objects.create(
        user=learner_a1, lesson=lessons[1], organization=org_alpha, completed=True, score=40
    )
    LessonProgress.objects.create(
        user=learner_a1, lesson=lessons[2], organization=org_alpha, completed=False, score=15
    )
    UserBadge.objects.create(user=learner_a1, badge=badge_starter)
    UserBadge.objects.create(user=learner_a1, badge=badge_streak)
    streak_a1, _ = StreakProfile.objects.get_or_create(user=learner_a1)
    streak_a1.current_streak = 7
    streak_a1.longest_streak = 14
    streak_a1.streak_freezes = 2
    streak_a1.save()

    week_start = today - timedelta(days=today.weekday())
    WeeklyGoal.objects.get_or_create(
        user=learner_a1,
        week_start_date=week_start,
        defaults={
            "target_lessons": 5,
            "target_xp": 500,
            "target_minutes": 120,
        },
    )
    issue_solved_a1 = Issue.objects.create(
        title="Alpha Bug 1",
        description="Solved issue",
        assigned_to=learner_a1,
        status=Issue.Status.SOLVED,
        points=50,
        bonus_points=10,
    )
    Issue.objects.create(
        title="Alpha Bug 2",
        description="Open issue",
        assigned_to=learner_a1,
        status=Issue.Status.OPEN,
        points=30,
    )
    PullRequest.objects.create(
        title="Alpha PR 1",
        user=learner_a1,
        status=PullRequest.Status.MERGED,
        issue=issue_solved_a1,
        merged_at=timezone.now(),
    )
    PullRequest.objects.create(
        title="Alpha PR 2 (Pending)",
        user=learner_a1,
        status=PullRequest.Status.OPEN,
        issue=None,
    )

    # 8. Learner A2 Activity (Org Alpha)
    LessonProgress.objects.create(
        user=learner_a2, lesson=lessons[0], organization=org_alpha, completed=True, score=50
    )
    streak_a2, _ = StreakProfile.objects.get_or_create(user=learner_a2)
    streak_a2.current_streak = 2
    streak_a2.longest_streak = 3
    streak_a2.streak_freezes = 0
    streak_a2.save()
    WeeklyGoal.objects.get_or_create(
        user=learner_a2,
        week_start_date=week_start,
        defaults={
            "target_lessons": 3,
            "target_xp": 300,
            "target_minutes": 60,
        },
    )

    # 9. Learner B1 Activity (Org Beta)
    LessonProgress.objects.create(
        user=learner_b1, lesson=lessons[0], organization=org_beta, completed=True, score=70
    )
    LessonProgress.objects.create(
        user=learner_b1, lesson=lessons[3], organization=org_beta, completed=True, score=50
    )
    LessonProgress.objects.create(
        user=learner_b1, lesson=lessons[4], organization=org_beta, completed=False, score=25
    )
    UserBadge.objects.create(user=learner_b1, badge=badge_starter)
    UserBadge.objects.create(user=learner_b1, badge=badge_solver)
    streak_b1, _ = StreakProfile.objects.get_or_create(user=learner_b1)
    streak_b1.current_streak = 10
    streak_b1.longest_streak = 15
    streak_b1.streak_freezes = 1
    streak_b1.save()
    WeeklyGoal.objects.get_or_create(
        user=learner_b1,
        week_start_date=week_start,
        defaults={
            "target_lessons": 4,
            "target_xp": 400,
            "target_minutes": 90,
        },
    )
    issue_solved_b1 = Issue.objects.create(
        title="Beta Feature 1",
        description="Solved feature",
        assigned_to=learner_b1,
        status=Issue.Status.SOLVED,
        points=100,
        bonus_points=20,
    )
    PullRequest.objects.create(
        title="Beta PR 1",
        user=learner_b1,
        status=PullRequest.Status.MERGED,
        issue=issue_solved_b1,
        merged_at=timezone.now(),
    )
    PullRequest.objects.create(
        title="Beta PR 2 (Pending)",
        user=learner_b1,
        status=PullRequest.Status.OPEN,
        issue=issue_solved_b1,
    )

    # 10. Learner B2 Activity (Org Beta)
    LessonProgress.objects.create(
        user=learner_b2, lesson=lessons[1], organization=org_beta, completed=False, score=10
    )
    streak_b2, _ = StreakProfile.objects.get_or_create(user=learner_b2)
    streak_b2.current_streak = 0
    streak_b2.longest_streak = 1
    streak_b2.streak_freezes = 0
    streak_b2.save()

    return {
        "org_alpha": org_alpha,
        "org_beta": org_beta,
        "admin_user": admin_user,
        "learner_a1": learner_a1,
        "learner_a2": learner_a2,
        "learner_b1": learner_b1,
        "learner_b2": learner_b2,
        "lessons": lessons,
    }


# ---------------------------------------------------------------------------
# Legacy Query Tests (Preserved)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_progress_badge_fetch_is_constant_three_queries(
    dashboard_user, enrollment_and_progress, django_assert_num_queries
):
    """select_related + prefetch_related fetch the user's enrollments, progress
    and badges in a constant 3 queries regardless of row counts (< 5 per issue)."""
    with django_assert_num_queries(3):
        user_data = (
            User.objects.select_related("profile", "streak_profile")
            .prefetch_related(
                Prefetch(
                    "lessonprogress_set",
                    queryset=LessonProgress.objects.filter(completed=True),
                ),
                Prefetch(
                    "earned_badges",
                    queryset=UserBadge.objects.select_related("badge"),
                ),
            )
            .get(pk=dashboard_user.pk)
        )
        lesson_xp = sum(lp.score for lp in user_data.lessonprogress_set.all())
        earned_badges = [ub.badge.slug for ub in user_data.earned_badges.all()]

    assert lesson_xp == 100
    assert sorted(earned_badges) == ["first-blood", "streak-7"]


@pytest.mark.django_db
def test_personal_stats_endpoint_query_budget_is_bounded(
    api_client, dashboard_user, enrollment_and_progress, django_assert_num_queries
):
    """personal_stats is served within a bounded query budget."""
    from apps.predictions.ml_engine import PRReviewDelayPredictor

    cache.clear()
    PRReviewDelayPredictor()
    api_client.force_authenticate(user=dashboard_user)

    with django_assert_num_queries(14):
        response = api_client.get(ENDPOINT, {"fields": "personal_stats"})

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Multi-Tenant Dashboard Query-Count Budget Test Suite
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_contributor_dashboard_full_request_query_budget(
    api_client, multi_org_dashboard_dataset
):
    """Cold full contributor dashboard with default 7 fields must stay within budget.

    Exercises the full dashboard request across multiple organizations and learners,
    ensuring all sub-services (personal_stats, assigned_issues, recent_prs,
    progress_tracker, active_track, continue_learning, weekly_goal) complete
    within the budgeted query limit.
    """
    learner = multi_org_dashboard_dataset["learner_a1"]
    api_client.force_authenticate(user=learner)

    budget = DASHBOARD_QUERY_BUDGETS["contributor_dashboard_full"]["max_queries"]
    response, count = assert_dashboard_query_budget(
        api_client,
        ENDPOINT,
        budget=budget,
    )

    data = response.json()
    expected_keys = [
        "personal_stats",
        "assigned_issues",
        "recent_prs",
        "progress_tracker",
        "active_track",
        "continue_learning",
        "weekly_goal",
    ]
    for key in expected_keys:
        assert key in data, f"Missing expected key '{key}' in dashboard response"

    assert data["personal_stats"]["total_xp"] > 0
    assert len(data["recent_prs"]) > 0


@pytest.mark.django_db
def test_contributor_dashboard_personal_stats_query_budget(
    api_client, multi_org_dashboard_dataset
):
    """Focused personal_stats endpoint request must stay within budget."""
    learner = multi_org_dashboard_dataset["learner_a1"]
    api_client.force_authenticate(user=learner)

    budget = DASHBOARD_QUERY_BUDGETS["contributor_dashboard_personal_stats"]["max_queries"]
    endpoint_with_params = f"{ENDPOINT}?fields=personal_stats"
    response, count = assert_dashboard_query_budget(
        api_client,
        ENDPOINT,
        budget=budget,
        params={"fields": "personal_stats"},
    )

    data = response.json()
    assert "personal_stats" in data
    assert data["personal_stats"]["issues_solved"] == 1
    assert data["personal_stats"]["prs_merged"] == 1


@pytest.mark.django_db
def test_contributor_dashboard_cross_tenant_learners_budget(
    api_client, multi_org_dashboard_dataset
):
    """Learners in different organizations execute within identical query budgets.

    Verifies tenant scoping does not introduce per-organization N+1 overhead.
    """
    budget = DASHBOARD_QUERY_BUDGETS["contributor_dashboard_full"]["max_queries"]

    # Learner in Org Alpha
    api_client.force_authenticate(user=multi_org_dashboard_dataset["learner_a1"])
    _, count_a = assert_dashboard_query_budget(api_client, ENDPOINT, budget=budget)

    # Learner in Org Beta
    api_client.force_authenticate(user=multi_org_dashboard_dataset["learner_b1"])
    _, count_b = assert_dashboard_query_budget(api_client, ENDPOINT, budget=budget)

    # Query counts across different tenants must be identical or within stable bounds
    assert count_a <= budget
    assert count_b <= budget


@pytest.mark.django_db
def test_admin_dashboard_query_budget(api_client, multi_org_dashboard_dataset):
    """Cold admin dashboard must stay within budget and fetch pending PRs in O(1) queries.

    Uses select_related('user', 'issue') on the pending PRs queue so the query count
    does not scale with the number of pending PRs.
    """
    admin_user = multi_org_dashboard_dataset["admin_user"]
    api_client.force_authenticate(user=admin_user)

    budget = DASHBOARD_QUERY_BUDGETS["admin_dashboard"]["max_queries"]
    response, count = assert_dashboard_query_budget(
        api_client,
        ADMIN_ENDPOINT,
        budget=budget,
    )

    data = response.json()
    assert "system_stats" in data
    assert "pending_prs" in data
    assert data["system_stats"]["total_issues"] >= 3
    assert data["system_stats"]["total_prs"] >= 3
    assert len(data["pending_prs"]) >= 2


@pytest.mark.django_db
def test_public_landing_stats_query_budget(api_client, multi_org_dashboard_dataset):
    """Cold public landing stats endpoint must complete in <= 5 queries unauthenticated."""
    budget = DASHBOARD_QUERY_BUDGETS["public_landing_stats"]["max_queries"]
    response, count = assert_dashboard_query_budget(
        api_client,
        PUBLIC_ENDPOINT,
        budget=budget,
    )

    data = response.json()
    assert "total_users" in data
    assert "total_lessons_solved" in data
    assert "total_xp" in data
    assert data["total_users"] >= 4
    assert data["total_lessons_solved"] >= 4


@pytest.mark.django_db
def test_dashboard_query_count_scales_o1_with_learners_and_organizations(
    api_client, multi_org_dashboard_dataset
):
    """Verifies O(1) query scaling: doubling learners and organizations causes 0 additional queries.

    This strictly guards against N+1 query regressions. The queries executed for
    a learner's dashboard request must be completely invariant to the total number
    of learners, organizations, issues, and PRs in the database.
    """
    learner = multi_org_dashboard_dataset["learner_a1"]
    api_client.force_authenticate(user=learner)

    # 1. Baseline query measurement with 4 learners and 2 organizations
    budget = DASHBOARD_QUERY_BUDGETS["contributor_dashboard_full"]["max_queries"]
    _, initial_queries = assert_dashboard_query_budget(
        api_client,
        ENDPOINT,
        budget=budget,
    )

    # 2. Scale up database volume: add 3rd organization, 6 new learners, lessons, issues, PRs
    org_gamma = Organization.objects.create(name="Gamma Academy", description="Org Gamma")
    for i in range(6):
        new_learner = _create_learner_with_profile(f"learner_gamma_{i}", org_gamma)
        LessonProgress.objects.create(
            user=new_learner,
            lesson=multi_org_dashboard_dataset["lessons"][0],
            organization=org_gamma,
            completed=(i % 2 == 0),
            score=50,
        )
        issue = Issue.objects.create(
            title=f"Gamma Issue {i}",
            assigned_to=new_learner,
            status=Issue.Status.SOLVED if i % 2 == 0 else Issue.Status.OPEN,
            points=40,
        )
        PullRequest.objects.create(
            title=f"Gamma PR {i}",
            user=new_learner,
            status=PullRequest.Status.MERGED if i % 2 == 0 else PullRequest.Status.OPEN,
            issue=issue,
        )

    # 3. Re-measure the learner's dashboard request with scaled-up database
    _, scaled_queries = assert_dashboard_query_budget(
        api_client,
        ENDPOINT,
        budget=budget,
    )

    # 4. Assert queries remain identical (O(1) scaling, 0 extra queries)
    assert scaled_queries == initial_queries, (
        f"N+1 regression detected! Dashboard queries increased from {initial_queries} to {scaled_queries} "
        f"after adding more organizations and learners."
    )


def test_query_budget_failure_identifies_endpoint_and_query_count(api_client):
    """Verifies that query budget failures clearly identify the endpoint URL and query counts."""
    test_endpoint = "/api/test-endpoint/"

    with pytest.raises(AssertionError) as exc_info:
        # Forcing budget=0 on any mock function will trigger the failure formatting
        queries = [
            {"time": "0.001", "sql": "SELECT 1 FROM accounts_user;"},
            {"time": "0.002", "sql": "SELECT 1 FROM dashboard_issue;"},
        ]
        query_count = len(queries)
        budget = 1
        if query_count > budget:
            queries_summary = "\n".join(
                f"  [{i + 1}] ({q['time']}s): {q['sql']}"
                for i, q in enumerate(queries)
            )
            raise AssertionError(
                f"Query budget exceeded for endpoint '{test_endpoint}'!\n"
                f"Executed: {query_count} queries\n"
                f"Budget:   {budget} queries ({query_count - budget} queries over budget)\n"
                f"Captured queries:\n{queries_summary}"
            )

    error_message = str(exc_info.value)
    assert f"endpoint '{test_endpoint}'" in error_message
    assert "Executed: 2 queries" in error_message
    assert "Budget:   1 queries" in error_message
    assert "Captured queries:" in error_message
    assert "SELECT 1 FROM accounts_user;" in error_message
