from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from apps.progress.models import ExerciseAttempt, QuizAttempt
from apps.content.models import Exercise, Lesson

class InsightsEngine:
    """
    Advanced learning analytics engine that evaluates user struggle areas 
    and dynamically generates hyper-personalized actionable feedback based on their
    accuracy and failure rates over a specified timeframe.
    """
    
    @classmethod
    def generate_weekly_insights(cls, user: User) -> dict:
        now = timezone.now()
        one_week_ago = now - timedelta(days=7)
        
        # 1. Analyze Failed Exercises
        recent_failed_exercises = ExerciseAttempt.objects.filter(
            user=user, 
            is_correct=False, 
            created_at__gte=one_week_ago
        ).select_related('exercise__lesson')
        
        # 2. Analyze Failed Quizzes
        recent_failed_quizzes = QuizAttempt.objects.filter(
            user=user,
            is_correct=False,
            created_at__gte=one_week_ago
        )
        
        # Frequency maps
        lesson_struggles = {}
        
        for attempt in recent_failed_exercises:
            lesson_slug = attempt.exercise.lesson.slug
            lesson_title = attempt.exercise.lesson.title
            lesson_struggles[lesson_slug] = lesson_struggles.get(lesson_slug, {"title": lesson_title, "count": 0})
            lesson_struggles[lesson_slug]["count"] += 1
            
        # Sort and find top struggle
        sorted_struggles = sorted(lesson_struggles.values(), key=lambda x: x["count"], reverse=True)
        top_struggle = sorted_struggles[0] if sorted_struggles else None
        
        insight_message = ""
        action_item = ""
        
        accuracy_score = cls._calculate_accuracy(user, one_week_ago)
        
        if top_struggle and top_struggle["count"] >= 3:
            insight_message = f"We noticed you had some trouble with '{top_struggle['title']}' this week."
            action_item = f"Reviewing the core concepts in '{top_struggle['title']}' could boost your mastery!"
        elif recent_failed_quizzes.count() > 5:
            insight_message = "You've been attempting a lot of quizzes! That's the spirit."
            action_item = "Try revisiting the reading materials before your next quiz attempt to improve accuracy."
        elif accuracy_score >= 90:
            insight_message = "You're demonstrating exceptional mastery with top-tier accuracy."
            action_item = "You're ready to tackle the advanced algorithmic challenges!"
        elif accuracy_score >= 70:
            insight_message = "You're on a solid steady learning path."
            action_item = "Keep exploring new topics to challenge yourself!"
        else:
            insight_message = "Learning is a journey, and mistakes are stepping stones."
            action_item = "Take your time with the materials and don't hesitate to ask for help on the forums."
            
        return {
            "insight_message": insight_message,
            "action_item": action_item,
            "struggle_areas": [s["title"] for s in sorted_struggles[:2]],
            "accuracy_score": accuracy_score,
            "total_failed_attempts": recent_failed_exercises.count() + recent_failed_quizzes.count()
        }
        
    @classmethod
    def _calculate_accuracy(cls, user: User, since: timezone.datetime) -> int:
        total_exercises = ExerciseAttempt.objects.filter(user=user, created_at__gte=since).count()
        correct_exercises = ExerciseAttempt.objects.filter(user=user, is_correct=True, created_at__gte=since).count()
        
        total_quizzes = QuizAttempt.objects.filter(user=user, created_at__gte=since).count()
        correct_quizzes = QuizAttempt.objects.filter(user=user, is_correct=True, created_at__gte=since).count()
        
        total = total_exercises + total_quizzes
        if total == 0:
            return 100
            
        return int(((correct_exercises + correct_quizzes) / total) * 100)
