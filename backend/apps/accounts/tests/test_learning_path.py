from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.content.models import Lesson
from apps.progress.models import Badge, LessonProgress, QuizAttempt, UserBadge

# All lesson slugs from curriculum.json — kept in sync with frontend/public/content/curriculum.json
ALL_SLUGS = [
    "what-is-open-source",
    "why-open-source-matters",
    "history-of-open-source",
    "benefits-of-contributing",
    "common-misconceptions",
    "open-source-licenses",
    "repositories-and-commits",
    "branches",
    "merging",
    "remotes",
    "git-workflow",
    "github-repositories",
    "forks",
    "pull-requests",
    "issues",
    "discussions",
    "organizations",
    "respect-and-communication",
    "read-readme-and-contributing",
    "professional-prs-and-issues",
    "maintainer-review-processes",
    "first-contribution-walkthrough",
    "contribution-lifecycle",
    "rebasing-and-squashing",
    "conflict-resolution",
    "code-reviews-and-cicd",
    "finding-projects",
    "hello-python",
    "hello-rust",
    "hello-javascript",
    "debugging-101",
]


class LearningPathTests(APITestCase):
    def setUp(self):
        # Create a user
        self.user = User.objects.create_user(username="learner", password="password123")
        self.url = reverse("learning-path")

        # Create Lesson records for all slugs (so curriculum modules are resolvable)
        for i, slug in enumerate(ALL_SLUGS):
            Lesson.objects.create(
                slug=slug,
                title=slug.replace("-", " ").title(),
                difficulty="beginner",
                order=i,
            )

    def test_unauthenticated_returns_401(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_basic_path(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("modules", response.data)
        self.assertIn("next_step", response.data)

        # Verify next_step is not None
        next_step = response.data["next_step"]
        self.assertIsNotNone(next_step)
        # Default next step should be module-1 as it is the first incomplete module
        self.assertEqual(next_step["id"], "module-1")
        self.assertEqual(next_step["status"], "not started")

    def test_scorer_prioritizes_in_progress_over_not_started(self):
        self.client.force_authenticate(user=self.user)

        # Mark first lesson of module-2 as in-progress (started but not completed)
        LessonProgress.objects.create(
            user=self.user,
            lesson=Lesson.objects.get(slug="repositories-and-commits"),
            completed=False,
        )

        # Mark all lessons of module-1 as not started (do nothing)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        modules = {m["id"]: m for m in response.data["modules"]}
        self.assertEqual(modules["module-1"]["status"], "not started")
        self.assertEqual(modules["module-2"]["status"], "in progress")

        # Because module-2 is in-progress, its base score (100) should be higher than module-1 (50)
        # even with sequence order boosts.
        self.assertEqual(response.data["next_step"]["id"], "module-2")

    def test_scorer_boosts_weak_quiz_areas(self):
        self.client.force_authenticate(user=self.user)

        # Mark module-1 first lesson as started
        LessonProgress.objects.create(
            user=self.user,
            lesson=Lesson.objects.get(slug="what-is-open-source"),
            completed=False,
        )

        # Mark module-2 first lesson as started
        LessonProgress.objects.create(
            user=self.user,
            lesson=Lesson.objects.get(slug="repositories-and-commits"),
            completed=False,
        )

        # Both modules are "in progress" now.
        # Let's create an incorrect quiz attempt for a lesson in module-2 (repositories-and-commits)
        QuizAttempt.objects.create(
            user=self.user,
            question_id="repositories-and-commits-q0",
            question_text="Sample text",
            selected_answer="Wrong",
            correct_answer="Right",
            is_correct=False,
        )

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        modules = {m["id"]: m for m in response.data["modules"]}
        # module-2 should get a +30 boost for weak quiz area, pushing its score above module-1
        self.assertIn(
            "Revisit this in-progress module to improve on previous quiz mistakes",
            modules["module-2"]["explanation"],
        )
        self.assertEqual(response.data["next_step"]["id"], "module-2")

    def test_scorer_handles_all_completed(self):
        self.client.force_authenticate(user=self.user)

        # Mark all lessons across every curriculum module as completed
        for slug in ALL_SLUGS:
            lesson = Lesson.objects.get(slug=slug)
            LessonProgress.objects.create(user=self.user, lesson=lesson, completed=True)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Every module should be completed
        for m in response.data["modules"]:
            self.assertEqual(m["status"], "completed")

        # Fallback recommended should be module-1 to review
        self.assertEqual(response.data["next_step"]["id"], "module-1")
        self.assertIn("Review this module", response.data["next_step"]["explanation"])
