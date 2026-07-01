import json
import os

from django.conf import settings
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.content.models import Lesson
from apps.progress.models import Badge, LessonProgress, QuizAttempt, UserBadge


class LearningPathTests(APITestCase):
    def setUp(self):
        # Create a user
        self.user = User.objects.create_user(username="learner", password="password123")
        self.url = reverse("learning-path")

        # Create some lessons that map to curriculum.json slugs
        # First module: mod-1 lessons
        self.l1 = Lesson.objects.create(
            slug="what-is-open-source",
            title="What is Open Source?",
            difficulty="beginner",
            order=0,
        )
        self.l2 = Lesson.objects.create(
            slug="why-open-source-matters",
            title="Why Open Source Matters",
            difficulty="beginner",
            order=1,
        )
        self.l3 = Lesson.objects.create(
            slug="history-of-open-source",
            title="History",
            difficulty="beginner",
            order=2,
        )
        self.l4 = Lesson.objects.create(
            slug="benefits-of-contributing",
            title="Benefits",
            difficulty="beginner",
            order=3,
        )
        self.l5 = Lesson.objects.create(
            slug="common-misconceptions",
            title="Misconceptions",
            difficulty="beginner",
            order=4,
        )

        # Second module: mod-2 lessons (all 5 from curriculum.json)
        self.l6 = Lesson.objects.create(
            slug="repositories-and-commits",
            title="Repositories & Commits",
            difficulty="beginner",
            order=5,
        )
        self.l7 = Lesson.objects.create(
            slug="branches",
            title="Branches",
            difficulty="beginner",
            order=6,
        )
        self.l8 = Lesson.objects.create(
            slug="merging",
            title="Merging",
            difficulty="beginner",
            order=7,
        )
        self.l9 = Lesson.objects.create(
            slug="remotes",
            title="Remotes",
            difficulty="beginner",
            order=8,
        )
        self.l10 = Lesson.objects.create(
            slug="git-workflow",
            title="Staging & Reviewing Status",
            difficulty="beginner",
            order=9,
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
        LessonProgress.objects.create(user=self.user, lesson=self.l6, completed=False)

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
        LessonProgress.objects.create(user=self.user, lesson=self.l1, completed=False)

        # Mark module-2 first lesson as started
        LessonProgress.objects.create(user=self.user, lesson=self.l6, completed=False)

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

        # Dynamically load curriculum to create all lessons
        curriculum_path = os.path.join(
            settings.BASE_DIR, "..", "frontend", "public", "content", "curriculum.json"
        )
        with open(curriculum_path) as f:
            curriculum = json.load(f)

        all_lessons = []
        order = 0
        for mod in curriculum["modules"]:
            for les_data in mod["lessons"]:
                lesson, _ = Lesson.objects.get_or_create(
                    slug=les_data["slug"],
                    defaults={
                        "title": les_data["title"],
                        "difficulty": les_data.get("difficulty", "beginner"),
                        "order": order,
                    },
                )
                all_lessons.append(lesson)
                order += 1

        # Mark all as completed
        for lesson in all_lessons:
            LessonProgress.objects.create(user=self.user, lesson=lesson, completed=True)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Every module should be completed
        for m in response.data["modules"]:
            self.assertEqual(m["status"], "completed")

        # Fallback recommended should be module-1 to review
        self.assertEqual(response.data["next_step"]["id"], "module-1")
        self.assertIn("Review this module", response.data["next_step"]["explanation"])
