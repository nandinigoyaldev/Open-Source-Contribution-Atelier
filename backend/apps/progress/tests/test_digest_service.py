from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()
from django.test import TestCase

from apps.progress.models import (
    XPEvent,
    LessonProgress,
    UserBadge,
    Badge,
    StreakProfile,
)
from apps.content.models import Lesson
from apps.accounts.models import UserProfile
from apps.progress.services.digest_service import WeeklyDigestService


class WeeklyDigestServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="password123"
        )
        # UserProfile is created automatically via signal in some apps, or we create it here
        if not hasattr(self.user, "profile"):
            UserProfile.objects.create(user=self.user)

        self.now = timezone.now()
        self.recent = self.now - timedelta(days=2)
        self.old = self.now - timedelta(days=10)

        # Create lessons
        self.lesson1 = Lesson.objects.create(title="Lesson 1", slug="lesson-1", order=1)
        self.lesson2 = Lesson.objects.create(title="Lesson 2", slug="lesson-2", order=2)
        self.lesson3 = Lesson.objects.create(title="Lesson 3", slug="lesson-3", order=3)
        self.lesson4 = Lesson.objects.create(title="Lesson 4", slug="lesson-4", order=4)

        # Create badge
        self.badge = Badge.objects.create(
            name="First Steps", slug="first-steps", description="First step."
        )

    def test_digest_with_no_activity(self):
        context = WeeklyDigestService.get_user_digest_context(self.user)
        self.assertEqual(context["xp_earned"], 0)
        self.assertEqual(context["total_xp"], 0)
        self.assertEqual(context["lessons_completed"], 0)
        self.assertEqual(context["quiz_challenge_count"], 0)
        self.assertEqual(context["current_streak"], 0)
        self.assertEqual(len(context["badges_earned"]), 0)
        self.assertEqual(context["rank"], 1)
        self.assertEqual(
            len(context["new_content"]), 4
        )  # Created all 4 lessons recently in setup
        self.assertEqual(len(context["recommendations"]), 3)

    def test_digest_with_recent_activity(self):
        # 1. Add XP
        XPEvent.objects.create(
            user=self.user, source_type="lesson", base_points=10, xp_delta=10
        )
        XPEvent.objects.create(
            user=self.user, source_type="exercise", base_points=20, xp_delta=20
        )

        # Manually alter created_at for older event (cannot do easily in create because of auto_now_add)
        old_xp = XPEvent.objects.create(
            user=self.user, source_type="lesson", base_points=50, xp_delta=50
        )
        XPEvent.objects.filter(pk=old_xp.pk).update(created_at=self.old)

        # 2. Add Lesson Progress
        LessonProgress.objects.create(
            user=self.user, lesson=self.lesson1, completed=True
        )

        old_lp = LessonProgress.objects.create(
            user=self.user, lesson=self.lesson2, completed=True
        )
        LessonProgress.objects.filter(pk=old_lp.pk).update(updated_at=self.old)

        # 3. Add Badges
        ub, _ = UserBadge.objects.get_or_create(user=self.user, badge=self.badge)

        old_ub = UserBadge.objects.create(
            user=self.user, badge=Badge.objects.create(name="Old Badge", slug="old")
        )
        UserBadge.objects.filter(pk=old_ub.pk).update(earned_at=self.old)

        # 4. Streak
        streak, _ = StreakProfile.objects.get_or_create(user=self.user)
        streak.current_streak = 5
        streak.save()

        context = WeeklyDigestService.get_user_digest_context(self.user)

        self.assertEqual(context["xp_earned"], 30)  # 10 + 20
        self.assertEqual(context["total_xp"], 80)  # 10 + 20 + 50
        self.assertEqual(context["lessons_completed"], 1)  # Only recent one
        self.assertEqual(context["quiz_challenge_count"], 1)  # One exercise
        self.assertEqual(context["current_streak"], 5)
        self.assertEqual(context["rank"], 1)
        self.assertEqual(len(context["new_content"]), 4)
        self.assertIn("First Steps", context["badges_earned"])
        self.assertNotIn("Old Badge", context["badges_earned"])

        # Check recommendations
        # Lesson 1 and 2 are completed. Lesson 3 and 4 should be recommended.
        self.assertIn("Lesson 3", context["recommendations"])
        self.assertIn("Lesson 4", context["recommendations"])
        self.assertNotIn("Lesson 1", context["recommendations"])
