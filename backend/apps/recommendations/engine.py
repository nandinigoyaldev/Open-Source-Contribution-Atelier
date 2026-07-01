from datetime import timedelta

from django.utils import timezone

from apps.challenges.models import Challenge
from apps.content.models import Lesson
from apps.progress.models import ExerciseAttempt, LessonProgress, QuizAttempt

from .models import Recommendation


class RecommendationEngine:
    def __init__(self, user):
        self.user = user

    def generate_recommendations(self):
        # Clear old generated ones that are not dismissed maybe?
        # For simplicity, we just generate new ones and rely on unique_together to avoid duplicates
        # or we just get or create

        self._generate_remedial_recommendations()
        self._generate_advanced_recommendations()
        self._generate_streak_recommendations()

    def _generate_remedial_recommendations(self):
        # Find recently failed quizzes
        recent_failed_quizzes = QuizAttempt.objects.filter(
            user=self.user, is_correct=False
        ).order_by("-created_at")[:5]

        for quiz in recent_failed_quizzes:
            # Recommend revisiting the lesson or trying again
            self._create_or_update_recommendation(
                content_type=Recommendation.ContentType.QUIZ,
                content_id=quiz.question_id,
                title=quiz.question_text[:50],
                reason="You recently struggled with this quiz. Try reviewing the topic and attempting it again.",
                priority_score=80,
            )

        # Find recently failed exercises
        recent_failed_exercises = (
            ExerciseAttempt.objects.filter(user=self.user, is_correct=False)
            .select_related("exercise")
            .order_by("-created_at")[:5]
        )

        for attempt in recent_failed_exercises:
            self._create_or_update_recommendation(
                content_type=Recommendation.ContentType.LESSON,
                content_id=str(attempt.exercise.lesson.id),  # assuming relation
                title=attempt.exercise.lesson.title,
                reason="You had some trouble with a recent coding exercise. Reviewing this lesson might help.",
                priority_score=75,
            )

    def _generate_advanced_recommendations(self):
        # Find completed lessons with high scores
        completed_lessons = LessonProgress.objects.filter(
            user=self.user, completed=True
        ).order_by("-score", "-updated_at")[:5]

        if completed_lessons.exists():
            # Recommend challenges
            challenges = Challenge.objects.all().order_by("?")[
                :3
            ]  # Random for now, can be improved
            for challenge in challenges:
                self._create_or_update_recommendation(
                    content_type=Recommendation.ContentType.CHALLENGE,
                    content_id=str(challenge.id),
                    title=challenge.title,
                    reason="You're doing great! Try testing your skills with this challenge.",
                    priority_score=60,
                )

    def _generate_streak_recommendations(self):
        # If user has no activity today, recommend a quick lesson
        today = timezone.localdate()
        recent_activity = LessonProgress.objects.filter(
            user=self.user, updated_at__date=today
        ).exists()

        if not recent_activity:
            # Find an uncompleted lesson
            uncompleted = Lesson.objects.exclude(
                lessonprogress__user=self.user, lessonprogress__completed=True
            ).first()

            if uncompleted:
                self._create_or_update_recommendation(
                    content_type=Recommendation.ContentType.LESSON,
                    content_id=str(uncompleted.id),
                    title=uncompleted.title,
                    reason="Keep your streak alive! Complete this quick lesson today.",
                    priority_score=90,
                )

    def _create_or_update_recommendation(
        self, content_type, content_id, title, reason, priority_score
    ):
        # Skip if already dismissed
        if Recommendation.objects.filter(
            user=self.user,
            content_type=content_type,
            content_id=content_id,
            is_dismissed=True,
        ).exists():
            return

        Recommendation.objects.update_or_create(
            user=self.user,
            content_type=content_type,
            content_id=content_id,
            defaults={
                "title": title,
                "reason": reason,
                "priority_score": priority_score,
            },
        )
