from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.cache import cache
from apps.accounts.models import UserProfile
from apps.organizations.models import Organization
from apps.content.models import Lesson, Organization as ContentOrganization
from apps.challenges.models import Challenge
from apps.progress.models import LessonProgress
from apps.recommendations.engine import RecommendationEngine
from apps.recommendations.models import Recommendation

User = get_user_model()


class RecommendationOrganizationIsolationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.org_a = Organization.objects.create(name="Org A")
        self.org_b = Organization.objects.create(name="Org B")

        self.content_org_a = ContentOrganization.objects.create(name="Org A", slug="org-a")
        self.content_org_b = ContentOrganization.objects.create(name="Org B", slug="org-b")

        self.user_a = User.objects.create_user(
            username="user_a", email="usera@orga.com", password="password123"
        )
        profile_a, _ = UserProfile.objects.get_or_create(user=self.user_a)
        profile_a.organization = self.org_a
        profile_a.save()

        self.user_b = User.objects.create_user(
            username="user_b", email="userb@orgb.com", password="password123"
        )
        profile_b, _ = UserProfile.objects.get_or_create(user=self.user_b)
        profile_b.organization = self.org_b
        profile_b.save()

    def test_streak_recommendation_respects_organization_isolation(self):
        """User in Org A must only get Org A or public lessons, not Org B private lessons."""
        lesson_a = Lesson.objects.create(
            title="Org A Private Lesson",
            slug="org-a-private-lesson",
            summary="Lesson for Org A",
            content="Content A",
            difficulty="beginner",
            organization=self.content_org_a,
        )
        lesson_b = Lesson.objects.create(
            title="Org B Private Lesson",
            slug="org-b-private-lesson",
            summary="Lesson for Org B",
            content="Content B",
            difficulty="beginner",
            organization=self.content_org_b,
        )

        engine_a = RecommendationEngine(self.user_a)
        engine_a.generate_recommendations()

        recs_a = Recommendation.objects.filter(
            user=self.user_a, content_type=Recommendation.ContentType.LESSON
        )
        rec_ids_a = [r.content_id for r in recs_a]
        self.assertIn(str(lesson_a.id), rec_ids_a)
        self.assertNotIn(str(lesson_b.id), rec_ids_a)

        engine_b = RecommendationEngine(self.user_b)
        engine_b.generate_recommendations()

        recs_b = Recommendation.objects.filter(
            user=self.user_b, content_type=Recommendation.ContentType.LESSON
        )
        rec_ids_b = [r.content_id for r in recs_b]
        self.assertIn(str(lesson_b.id), rec_ids_b)
        self.assertNotIn(str(lesson_a.id), rec_ids_b)

    def test_advanced_recommendation_respects_organization_isolation(self):
        """User in Org A must only get Org A or public challenges, not Org B private challenges."""
        # Create a completed lesson progress so advanced recommendations trigger
        lesson = Lesson.objects.create(
            title="Public Lesson",
            slug="public-lesson-1",
            summary="Public lesson",
            content="Content",
            difficulty="beginner",
        )
        LessonProgress.objects.create(
            user=self.user_a, lesson=lesson, completed=True, score=95
        )

        challenge_a = Challenge.objects.create(
            title="Org A Challenge",
            slug="org-a-challenge",
            summary="Org A challenge",
            difficulty="intermediate",
            organization=self.org_a,
            is_public=False,
        )
        challenge_b = Challenge.objects.create(
            title="Org B Challenge",
            slug="org-b-challenge",
            summary="Org B challenge",
            difficulty="intermediate",
            organization=self.org_b,
            is_public=False,
        )

        engine_a = RecommendationEngine(self.user_a)
        engine_a.generate_recommendations()

        recs_a = Recommendation.objects.filter(
            user=self.user_a, content_type=Recommendation.ContentType.CHALLENGE
        )
        rec_ids_a = [r.content_id for r in recs_a]
        self.assertIn(str(challenge_a.id), rec_ids_a)
        self.assertNotIn(str(challenge_b.id), rec_ids_a)

    def test_public_content_accessible_to_all_organizations(self):
        """Global public lessons without organization should be accessible to any user."""
        public_lesson = Lesson.objects.create(
            title="Global Public Lesson",
            slug="global-public-lesson",
            summary="Public lesson for all",
            content="Public content",
            difficulty="beginner",
            organization=None,
        )

        engine_a = RecommendationEngine(self.user_a)
        engine_a.generate_recommendations()

        recs_a = Recommendation.objects.filter(
            user=self.user_a, content_type=Recommendation.ContentType.LESSON
        )
        rec_ids_a = [r.content_id for r in recs_a]
        self.assertIn(str(public_lesson.id), rec_ids_a)
