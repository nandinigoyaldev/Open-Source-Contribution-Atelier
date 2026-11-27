from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.progress.models import (
    ExerciseAttempt,
    QuizAttempt,
    StreakProfile,
    StreakRecoveryPlan,
)

get_user_model()


class StreakRecoveryService:
    @classmethod
    def get_or_create_recovery_plan(cls, user):
        """
        Check if the user has missed yesterday's streak day.
        If yes, get or create a StreakRecoveryPlan for today.
        """
        try:
            profile = StreakProfile.objects.get(user=user)
        except StreakProfile.DoesNotExist:
            return None

        last_date = profile.last_activity_date
        if not last_date:
            return None

        try:
            today = user.user_profile.local_today
        except Exception:
            today = date.today()
        diff = today - last_date

        with transaction.atomic():
            # If they missed exactly yesterday
            if diff == timedelta(days=2):
                plan, created = StreakRecoveryPlan.objects.get_or_create(
                    user=user,
                    defaults={
                        "target_date": today,
                        "previous_streak": profile.current_streak,
                        "quiz_target": 1,
                        "reading_target": 15,
                        "code_target": 1,
                    },
                )

                if not created and plan.target_date != today:
                    # Clean up expired plan
                    plan.delete()
                    plan = StreakRecoveryPlan.objects.create(
                        user=user,
                        target_date=today,
                        previous_streak=profile.current_streak,
                        quiz_target=1,
                        reading_target=15,
                        code_target=1,
                    )

                # Sync progress automatically when retrieved
                cls.sync_and_update_progress(plan)
                return plan

            # If they are not eligible for recovery, clean up any old plan
            StreakRecoveryPlan.objects.filter(user=user).delete()
            return None

    @classmethod
    def sync_and_update_progress(cls, plan):
        """
        Query actual completions for today and evaluate if recovery is complete.
        """
        if plan.is_completed:
            return plan

        today = plan.target_date

        # Count only correctly answered quizzes
        plan.quiz_progress = QuizAttempt.objects.filter(
            user=plan.user,
            created_at__date=today,
            is_correct=True,
        ).count()

        # Count only successful coding exercises
        plan.code_progress = ExerciseAttempt.objects.filter(
            user=plan.user,
            is_correct=True,
            created_at__date=today,
        ).count()

        # Check if fully recovered
        if (
            plan.quiz_progress >= plan.quiz_target
            and plan.reading_progress >= plan.reading_target
            and plan.code_progress >= plan.code_target
        ):
            plan.is_completed = True

            try:
                profile = StreakProfile.objects.get(user=plan.user)
                profile.current_streak = plan.previous_streak + 1
                profile.last_activity_date = today

                if profile.current_streak > profile.longest_streak:
                    profile.longest_streak = profile.current_streak

                # Leave streak_freezes alone, a freeze may be spent meanwhile.
                profile.save(
                    update_fields=[
                        "current_streak",
                        "longest_streak",
                        "last_activity_date",
                        "updated_at",
                    ]
                )

            except StreakProfile.DoesNotExist:
                pass

        plan.save()
        return plan

    @classmethod
    def record_reading_minute(cls, user):
        """
        Record one reading minute toward the active recovery plan.
        Returns True if the plan was updated.
        """
        plan = cls.get_or_create_recovery_plan(user)

        if not plan or plan.is_completed:
            return False

        now = timezone.now()
        elapsed = (now - plan.updated_at).total_seconds()

        # Always allow the first increment, then throttle to once every 30 seconds.
        if plan.reading_progress == 0 or elapsed >= 30:
            plan.reading_progress = min(
                plan.reading_target,
                plan.reading_progress + 1,
            )
            plan.save()
            cls.sync_and_update_progress(plan)
            return True

        return False
