"""
Tests for the Learning Analytics services.
"""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from apps.learning_analytics.models import (
    DailyLearningMetric,
    LearningGoal,
    LearningInsight,
    LearningSession,
    SkillTag,
    UserSkillProfile,
)
from apps.learning_analytics.services import (
    compute_all_skill_levels,
    compute_daily_metrics,
    compute_skill_level,
    generate_insights,
    generate_monthly_recap,
    generate_weekly_summary,
    get_analytics_dashboard,
)
from apps.learning_analytics.utils import (
    compute_velocity,
    get_current_streak,
    predict_completion,
)


class SkillTagModelTest(TestCase):
    """Tests for SkillTag model."""

    def setUp(self):
        self.tag = SkillTag.objects.create(
            name="Git Basics",
            slug="git-basics",
            description="Version control fundamentals",
            icon_emoji="🔀",
        )

    def test_str(self):
        self.assertEqual(str(self.tag), "Git Basics")

    def test_slug_unique(self):
        with self.assertRaises(Exception):
            SkillTag.objects.create(
                name="Git Basics 2",
                slug="git-basics",
            )

    def test_parent_child(self):
        child = SkillTag.objects.create(
            name="Git Branching",
            slug="git-branching",
            parent=self.tag,
        )
        self.assertEqual(child.parent, self.tag)
        self.assertIn(child, self.tag.children.all())


class LearningSessionModelTest(TestCase):
    """Tests for LearningSession model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.tag = SkillTag.objects.create(name="Python", slug="python")

    def test_create_session(self):
        session = LearningSession.objects.create(
            user=self.user,
            activity_type="lesson",
            duration_seconds=300,
            xp_earned=25,
            score=85,
            completed=True,
        )
        self.assertEqual(session.user, self.user)
        self.assertEqual(session.activity_type, "lesson")
        self.assertTrue(session.completed)

    def test_str(self):
        session = LearningSession.objects.create(
            user=self.user,
            activity_type="quiz",
            duration_seconds=120,
        )
        self.assertIn("testuser", str(session))
        self.assertIn("quiz", str(session))

    def test_end_session(self):
        session = LearningSession.objects.create(
            user=self.user,
            activity_type="exercise",
        )
        session.end_session(score=90, completed=True)
        self.assertIsNotNone(session.ended_at)
        self.assertTrue(session.completed)


class UserSkillProfileModelTest(TestCase):
    """Tests for UserSkillProfile model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.tag = SkillTag.objects.create(name="Django", slug="django")

    def test_create_profile(self):
        profile = UserSkillProfile.objects.create(
            user=self.user,
            skill_tag=self.tag,
            level=45,
            total_sessions=10,
            total_xp=200,
            average_score=78.5,
        )
        self.assertEqual(profile.level, 45)
        self.assertEqual(profile.trend, "stable")

    def test_unique_together(self):
        UserSkillProfile.objects.create(
            user=self.user,
            skill_tag=self.tag,
            level=30,
        )
        with self.assertRaises(Exception):
            UserSkillProfile.objects.create(
                user=self.user,
                skill_tag=self.tag,
                level=50,
            )

    def test_str(self):
        profile = UserSkillProfile.objects.create(
            user=self.user, skill_tag=self.tag, level=60
        )
        self.assertIn("testuser", str(profile))
        self.assertIn("Lv.60", str(profile))


class LearningInsightModelTest(TestCase):
    """Tests for LearningInsight model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )

    def test_create_insight(self):
        insight = LearningInsight.objects.create(
            user=self.user,
            insight_type="streak",
            title="Great streak!",
            body="You're on a 5-day streak!",
            priority=2,
        )
        self.assertFalse(insight.is_read)
        self.assertFalse(insight.is_dismissed)

    def test_is_expired_no_expiry(self):
        insight = LearningInsight.objects.create(
            user=self.user,
            insight_type="tip",
            title="Test",
            body="Body",
        )
        self.assertFalse(insight.is_expired)

    def test_is_expired_with_future(self):
        insight = LearningInsight.objects.create(
            user=self.user,
            insight_type="tip",
            title="Test",
            body="Body",
            expires_at=timezone.now() + timedelta(days=1),
        )
        self.assertFalse(insight.is_expired)

    def test_is_expired_with_past(self):
        insight = LearningInsight.objects.create(
            user=self.user,
            insight_type="tip",
            title="Test",
            body="Body",
            expires_at=timezone.now() - timedelta(days=1),
        )
        self.assertTrue(insight.is_expired)

    def test_str(self):
        insight = LearningInsight.objects.create(
            user=self.user,
            insight_type="tip",
            title="Pro Tip",
            body="Body",
        )
        self.assertIn("[tip]", str(insight))
        self.assertIn("Pro Tip", str(insight))


class DailyLearningMetricModelTest(TestCase):
    """Tests for DailyLearningMetric model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )

    def test_create_metric(self):
        metric = DailyLearningMetric.objects.create(
            user=self.user,
            date=timezone.now().date(),
            total_minutes=45,
            lessons_completed=2,
            xp_earned=75,
            focus_score=0.85,
        )
        self.assertEqual(metric.total_minutes, 45)
        self.assertEqual(metric.focus_score, 0.85)

    def test_unique_constraint(self):
        today = timezone.now().date()
        DailyLearningMetric.objects.create(user=self.user, date=today, total_minutes=30)
        with self.assertRaises(Exception):
            DailyLearningMetric.objects.create(
                user=self.user, date=today, total_minutes=60
            )

    def test_str(self):
        metric = DailyLearningMetric.objects.create(
            user=self.user,
            date=timezone.now().date(),
            total_minutes=30,
            xp_earned=50,
        )
        self.assertIn("testuser", str(metric))
        self.assertIn("30min", str(metric))


class LearningGoalModelTest(TestCase):
    """Tests for LearningGoal model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )

    def test_create_goal(self):
        goal = LearningGoal.objects.create(
            user=self.user,
            goal_type="xp_target",
            title="Reach 1000 XP",
            target_value=1000,
            current_value=350,
        )
        self.assertEqual(goal.progress_pct, 35)
        self.assertFalse(goal.is_completed)

    def test_progress_pct_zero_target(self):
        goal = LearningGoal.objects.create(
            user=self.user,
            goal_type="lesson_count",
            title="Zero target",
            target_value=0,
        )
        self.assertEqual(goal.progress_pct, 0)

    def test_progress_pct_complete(self):
        goal = LearningGoal.objects.create(
            user=self.user,
            goal_type="lesson_count",
            title="Complete",
            target_value=10,
            current_value=10,
        )
        self.assertEqual(goal.progress_pct, 100)

    def test_progress_pct_capped_at_100(self):
        goal = LearningGoal.objects.create(
            user=self.user,
            goal_type="lesson_count",
            title="Overachieve",
            target_value=10,
            current_value=15,
        )
        self.assertEqual(goal.progress_pct, 100)

    def test_is_overdue(self):
        goal = LearningGoal.objects.create(
            user=self.user,
            goal_type="xp_target",
            title="Overdue",
            target_value=100,
            deadline=timezone.now().date() - timedelta(days=1),
        )
        self.assertTrue(goal.is_overdue)

    def test_not_overdue_when_completed(self):
        goal = LearningGoal.objects.create(
            user=self.user,
            goal_type="xp_target",
            title="Done",
            target_value=100,
            is_completed=True,
            deadline=timezone.now().date() - timedelta(days=1),
        )
        self.assertFalse(goal.is_overdue)

    def test_str(self):
        goal = LearningGoal.objects.create(
            user=self.user,
            goal_type="xp_target",
            title="My Goal",
            target_value=500,
            current_value=200,
        )
        self.assertIn("testuser", str(goal))
        self.assertIn("200/500", str(goal))


class ComputeSkillLevelTest(TestCase):
    """Tests for the compute_skill_level service function."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.tag = SkillTag.objects.create(name="React", slug="react")

    def test_no_sessions_returns_zero(self):
        result = compute_skill_level(self.user, self.tag)
        self.assertEqual(result["level"], 0)
        self.assertEqual(result["total_sessions"], 0)
        self.assertIsNone(result["last_practiced"])

    def test_with_sessions(self):
        now = timezone.now()
        session = LearningSession.objects.create(
            user=self.user,
            activity_type="lesson",
            started_at=now,
            ended_at=now,
            duration_seconds=300,
            xp_earned=50,
            score=80,
            completed=True,
        )
        session.skill_tags.create(skill_tag=self.tag)

        result = compute_skill_level(self.user, self.tag)
        self.assertGreater(result["level"], 0)
        self.assertEqual(result["total_sessions"], 1)
        self.assertEqual(result["total_xp"], 50)

    def test_trend_detection(self):
        """Two weeks ago activity but not this week should be declining."""
        now = timezone.now()
        two_weeks_ago = now - timedelta(days=15)

        session = LearningSession.objects.create(
            user=self.user,
            activity_type="lesson",
            started_at=two_weeks_ago,
            duration_seconds=200,
            completed=True,
        )
        session.skill_tags.create(skill_tag=self.tag)

        result = compute_skill_level(self.user, self.tag)
        self.assertIn(result["trend"], ("stable", "declining"))


class ComputeAllSkillLevelsTest(TestCase):
    """Tests for compute_all_skill_levels."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.tag1 = SkillTag.objects.create(name="Python", slug="python")
        self.tag2 = SkillTag.objects.create(name="Django", slug="django")

    def test_empty_returns_empty(self):
        result = compute_all_skill_levels(self.user)
        self.assertEqual(len(result), 0)

    def test_returns_only_practised(self):
        now = timezone.now()
        session = LearningSession.objects.create(
            user=self.user,
            activity_type="lesson",
            started_at=now,
            duration_seconds=100,
            completed=True,
        )
        session.skill_tags.create(skill_tag=self.tag1)

        result = compute_all_skill_levels(self.user)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["skill_tag"].slug, "python")


class ComputeDailyMetricsTest(TestCase):
    """Tests for compute_daily_metrics."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )

    def test_no_sessions(self):
        metric = compute_daily_metrics(self.user)
        self.assertEqual(metric.total_minutes, 0)
        self.assertEqual(metric.lessons_completed, 0)

    def test_with_sessions(self):
        now = timezone.now()
        LearningSession.objects.create(
            user=self.user,
            activity_type="lesson",
            started_at=now,
            duration_seconds=600,
            xp_earned=30,
            completed=True,
        )
        LearningSession.objects.create(
            user=self.user,
            activity_type="quiz",
            started_at=now,
            duration_seconds=180,
            score=85,
            xp_earned=20,
            completed=True,
        )

        metric = compute_daily_metrics(self.user)
        self.assertGreater(metric.total_minutes, 0)
        self.assertEqual(metric.lessons_completed, 1)
        self.assertEqual(metric.quizzes_taken, 1)
        self.assertGreater(metric.xp_earned, 0)

    def test_updates_existing_metric(self):
        today = timezone.now().date()
        DailyLearningMetric.objects.create(user=self.user, date=today, total_minutes=10)

        now = timezone.now()
        LearningSession.objects.create(
            user=self.user,
            activity_type="lesson",
            started_at=now,
            duration_seconds=1200,
            xp_earned=50,
        )

        metric = compute_daily_metrics(self.user, today)
        self.assertEqual(DailyLearningMetric.objects.filter(user=self.user).count(), 1)


class GenerateInsightsTest(TestCase):
    """Tests for generate_insights."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )

    def test_no_crash_on_empty(self):
        """Should not crash even when user has no data."""
        insights = generate_insights(self.user)
        self.assertIsInstance(insights, list)

    def test_streak_insight_with_profile(self):
        from apps.progress.models import StreakProfile

        StreakProfile.objects.create(
            user=self.user,
            current_streak=10,
            longest_streak=15,
        )
        insights = generate_insights(self.user)
        streak_insights = [i for i in insights if i["insight_type"] == "streak"]
        self.assertTrue(len(streak_insights) > 0)
        self.assertIn("10-day", streak_insights[0]["title"])

    def test_no_duplicates(self):
        """Generating insights twice should not create duplicates."""
        from apps.progress.models import StreakProfile

        StreakProfile.objects.create(user=self.user, current_streak=7, longest_streak=7)
        generate_insights(self.user)
        count_after_first = LearningInsight.objects.filter(user=self.user).count()

        generate_insights(self.user)
        count_after_second = LearningInsight.objects.filter(user=self.user).count()

        self.assertEqual(count_after_first, count_after_second)


class ComputeVelocityTest(TestCase):
    """Tests for compute_velocity."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )

    def test_no_data(self):
        velocity = compute_velocity(self.user, days=7)
        self.assertEqual(velocity["minutes_per_day"], 0)
        self.assertEqual(velocity["xp_per_day"], 0)

    def test_with_data(self):
        today = timezone.now().date()
        DailyLearningMetric.objects.create(
            user=self.user,
            date=today,
            total_minutes=30,
            xp_earned=50,
        )
        velocity = compute_velocity(self.user, days=7)
        self.assertGreater(velocity["minutes_per_day"], 0)


class PredictCompletionTest(TestCase):
    """Tests for predict_completion."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.goal = LearningGoal.objects.create(
            user=self.user,
            goal_type="xp_target",
            title="1000 XP",
            target_value=1000,
            current_value=500,
        )

    def test_completed_goal(self):
        self.goal.is_completed = True
        self.goal.save()
        result = predict_completion(self.user, self.goal)
        self.assertEqual(result["confidence"], "completed")

    def test_immediate_completion(self):
        self.goal.current_value = 1000
        self.goal.save()
        result = predict_completion(self.user, self.goal)
        self.assertEqual(result["confidence"], "immediate")

    def test_no_activity(self):
        result = predict_completion(self.user, self.goal)
        self.assertEqual(result["confidence"], "unknown")

    def test_with_activity(self):
        today = timezone.now().date()
        for i in range(14):
            DailyLearningMetric.objects.create(
                user=self.user,
                date=today - timedelta(days=i),
                total_minutes=30,
                xp_earned=50,
            )
        result = predict_completion(self.user, self.goal)
        self.assertIn("estimated_date", result)
        self.assertIn("confidence", result)


class GenerateWeeklySummaryTest(TestCase):
    """Tests for generate_weekly_summary."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )

    def test_empty_summary(self):
        summary = generate_weekly_summary(self.user)
        self.assertIn("period", summary)
        self.assertIn("summary", summary)
        self.assertIn("recommendations", summary)

    def test_with_data(self):
        today = timezone.now().date()
        DailyLearningMetric.objects.create(
            user=self.user,
            date=today,
            total_minutes=60,
            xp_earned=100,
            lessons_completed=2,
            average_quiz_score=80,
            focus_score=0.9,
        )
        summary = generate_weekly_summary(self.user)
        self.assertGreater(summary["summary"]["total_minutes"], 0)


class GenerateMonthlyRecapTest(TestCase):
    """Tests for generate_monthly_recap."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )

    def test_empty_recap(self):
        recap = generate_monthly_recap(self.user)
        self.assertIn("this_month", recap)
        self.assertIn("last_month", recap)
        self.assertIn("growth", recap)

    def test_with_data(self):
        today = timezone.now().date()
        DailyLearningMetric.objects.create(
            user=self.user,
            date=today,
            total_minutes=120,
            xp_earned=200,
        )
        recap = generate_monthly_recap(self.user)
        self.assertGreater(recap["this_month"]["total_minutes"], 0)


class GetAnalyticsDashboardTest(TestCase):
    """Tests for get_analytics_dashboard."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )

    def test_empty_dashboard(self):
        data = get_analytics_dashboard(self.user, days=30)
        self.assertIn("summary", data)
        self.assertIn("charts", data)
        self.assertIn("skill_levels", data)
        self.assertIn("active_goals", data)
        self.assertEqual(data["summary"]["total_minutes"], 0)

    def test_with_data(self):
        today = timezone.now().date()
        DailyLearningMetric.objects.create(
            user=self.user,
            date=today,
            total_minutes=45,
            xp_earned=75,
            lessons_completed=1,
        )
        data = get_analytics_dashboard(self.user, days=30)
        self.assertEqual(data["summary"]["total_minutes"], 45)
        self.assertEqual(len(data["charts"]["dates"]), 1)


class GetCurrentStreakTest(TestCase):
    """Tests for get_current_streak."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )

    def test_no_activity(self):
        streak = get_current_streak(self.user)
        self.assertEqual(streak, 0)

    def test_single_day(self):
        today = timezone.now().date()
        DailyLearningMetric.objects.create(user=self.user, date=today, total_minutes=30)
        streak = get_current_streak(self.user)
        self.assertEqual(streak, 1)

    def test_consecutive_days(self):
        today = timezone.now().date()
        for i in range(5):
            DailyLearningMetric.objects.create(
                user=self.user,
                date=today - timedelta(days=i),
                total_minutes=30,
            )
        streak = get_current_streak(self.user)
        self.assertEqual(streak, 5)

    def test_broken_streak(self):
        today = timezone.now().date()
        DailyLearningMetric.objects.create(user=self.user, date=today, total_minutes=30)
        DailyLearningMetric.objects.create(
            user=self.user,
            date=today - timedelta(days=2),
            total_minutes=30,
        )
        streak = get_current_streak(self.user)
        self.assertEqual(streak, 1)


class SkillProfilingQueryBudgetAndParityTest(TestCase):
    """Tests verifying bounded query budget (<= 5 queries) and output parity."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="perfuser", password="perfpass123"
        )
        self.tags = [
            SkillTag.objects.create(name=f"Skill {i}", slug=f"skill-{i}")
            for i in range(10)
        ]

    def test_query_budget_bounded_o1(self):
        now = timezone.now()
        # Create multiple sessions across all 10 skills
        for i, tag in enumerate(self.tags):
            for j in range(3):
                session = LearningSession.objects.create(
                    user=self.user,
                    activity_type="lesson",
                    started_at=now - timedelta(days=j),
                    duration_seconds=120 * (j + 1),
                    xp_earned=25 * (j + 1),
                    score=70 + (j * 10),
                    completed=True,
                )
                session.skill_tags.create(skill_tag=tag)

        # Assert compute_all_skill_levels runs in <= 5 queries (O(1) with respect to skills)
        with self.assertNumQueries(2):
            results = compute_all_skill_levels(self.user)

        self.assertEqual(len(results), 10)

    def test_data_parity_with_single_skill_computation(self):
        now = timezone.now()
        tag = self.tags[0]
        # Session 1: this week with score
        s1 = LearningSession.objects.create(
            user=self.user,
            activity_type="lesson",
            started_at=now - timedelta(days=2),
            duration_seconds=300,
            xp_earned=50,
            score=85,
            completed=True,
        )
        s1.skill_tags.create(skill_tag=tag)

        # Session 2: last week without score
        s2 = LearningSession.objects.create(
            user=self.user,
            activity_type="quiz",
            started_at=now - timedelta(days=10),
            duration_seconds=180,
            xp_earned=30,
            score=None,
            completed=True,
        )
        s2.skill_tags.create(skill_tag=tag)

        single_result = compute_skill_level(self.user, tag)
        all_results = compute_all_skill_levels(self.user)
        self.assertEqual(len(all_results), 1)
        grouped_result = all_results[0]

        self.assertEqual(grouped_result["skill_tag"].id, tag.id)
        self.assertEqual(grouped_result["level"], single_result["level"])
        self.assertEqual(
            grouped_result["total_sessions"], single_result["total_sessions"]
        )
        self.assertEqual(grouped_result["total_xp"], single_result["total_xp"])
        self.assertEqual(
            grouped_result["average_score"], single_result["average_score"]
        )
        self.assertEqual(grouped_result["trend"], single_result["trend"])

    def test_edge_case_zero_sessions_and_null_scores(self):
        tag_empty = SkillTag.objects.create(name="Empty", slug="empty")
        res_single = compute_skill_level(self.user, tag_empty)
        self.assertEqual(res_single["level"], 0)
        self.assertEqual(res_single["total_sessions"], 0)
        self.assertEqual(res_single["total_xp"], 0)
        self.assertEqual(res_single["average_score"], 0.0)
        self.assertIsNone(res_single["last_practiced"])
        self.assertEqual(res_single["trend"], "stable")
