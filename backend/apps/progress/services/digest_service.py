from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()
from django.db.models import Sum

from apps.content.models import Lesson
from apps.progress.models import LessonProgress, StreakProfile, UserBadge, XPEvent
from apps.progress.services.insights_engine import InsightsEngine


class WeeklyDigestService:
    @classmethod
    def get_cached_leaderboard(cls):
        from django.core.cache import cache

        leaderboard = cache.get("weekly_digest_leaderboard")
        if not leaderboard:
            users = (
                User.objects.filter(is_active=True)
                .annotate(total_xp=Sum("xp_events__xp_delta"))
                .order_by("-total_xp")
            )
            leaderboard = {u.id: rank for rank, u in enumerate(users, start=1)}
            cache.set("weekly_digest_leaderboard", leaderboard, 60 * 60)
        return leaderboard

    @classmethod
    def get_user_digest_context(cls, user: User) -> dict:
        now = timezone.now()
        one_week_ago = now - timedelta(days=7)

        # 1. XP Earned in the last week
        xp_events = XPEvent.objects.filter(user=user, created_at__gte=one_week_ago)
        xp_earned = xp_events.aggregate(total=Sum("xp_delta"))["total"] or 0

        # 2. Lessons Completed in the last week
        lessons_completed = LessonProgress.objects.filter(
            user=user, updated_at__gte=one_week_ago, completed=True
        ).count()

        # 3. Quizzes and Challenges
        quiz_challenge_count = xp_events.filter(
            source_type__in=["exercise", "quiz", "challenge"]
        ).count()

        # 4. Current Streak & Streak Risk Check
        streak = StreakProfile.objects.filter(user=user).first()
        current_streak = streak.current_streak if streak else 0
        today = now.date()
        streak_at_risk = bool(
            current_streak > 0
            and (
                not streak
                or not streak.last_activity_date
                or streak.last_activity_date < today
            )
        )

        # 5. Newly unlocked badges
        badges_earned_qs = UserBadge.objects.filter(
            user=user, earned_at__gte=one_week_ago
        ).select_related("badge")
        badges_earned_details = [
            {
                "name": ub.badge.name,
                "description": ub.badge.description,
                "icon": ub.badge.icon_asset_url or "🏅",
            }
            for ub in badges_earned_qs
        ]
        badge_names = [b["name"] for b in badges_earned_details]

        # 6. Leaderboard / Total XP
        user_total_xp = (
            XPEvent.objects.filter(user=user).aggregate(total=Sum("xp_delta"))["total"]
            or 0
        )

        # Calculate Rank (Optimized via global cache)
        leaderboard = cls.get_cached_leaderboard()
        rank = leaderboard.get(user.id, User.objects.count())

        # 7. Learning Path / Skill Tree Progress
        total_lessons_count = Lesson.objects.count()
        completed_lesson_ids = set(
            LessonProgress.objects.filter(user=user, completed=True).values_list(
                "lesson_id", flat=True
            )
        )
        overall_completed_count = len(completed_lesson_ids)
        overall_progress_percent = (
            round((overall_completed_count / total_lessons_count) * 100, 1)
            if total_lessons_count > 0
            else 0.0
        )

        from apps.content.models import LearningPath

        paths_data = []
        for path in LearningPath.objects.filter(is_published=True).prefetch_related("lessons"):
            path_lessons = list(path.lessons.all())
            path_total = len(path_lessons)
            if path_total > 0:
                path_completed = sum(1 for l in path_lessons if l.id in completed_lesson_ids)
                path_pct = round((path_completed / path_total) * 100, 1)
                paths_data.append(
                    {
                        "title": path.title,
                        "completed": path_completed,
                        "total": path_total,
                        "percentage": path_pct,
                    }
                )

        learning_path_progress = {
            "completed_count": overall_completed_count,
            "total_count": total_lessons_count,
            "percentage": overall_progress_percent,
            "paths": paths_data,
        }

        # 8. Recommendations (Suggested Next Steps based on user's path)
        recommended_lessons = Lesson.objects.exclude(
            id__in=completed_lesson_ids
        ).order_by("order")[:3]
        recommendation_list = [
            {"title": lesson.title, "summary": lesson.summary, "slug": lesson.slug}
            for lesson in recommended_lessons
        ]
        recommendations = [r["title"] for r in recommendation_list]

        # 9. Newly Released Content
        new_lessons = Lesson.objects.all().order_by("-id")[:4]
        new_content = [lesson.title for lesson in new_lessons]

        # 10. Advanced Insights
        insights = InsightsEngine.generate_weekly_insights(user)

        return {
            "user": user,
            "username": user.username,
            "xp_earned": xp_earned,
            "total_xp": user_total_xp,
            "rank": rank,
            "lessons_completed": lessons_completed,
            "quiz_challenge_count": quiz_challenge_count,
            "current_streak": current_streak,
            "streak_at_risk": streak_at_risk,
            "badges_earned": badge_names,
            "badges_earned_details": badges_earned_details,
            "learning_path_progress": learning_path_progress,
            "recommendations": recommendations,
            "recommendation_details": recommendation_list,
            "new_content": new_content,
            "insights": insights,
            "start_date": one_week_ago.strftime("%B %d, %Y"),
            "end_date": now.strftime("%B %d, %Y"),
        }

