from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Sum

from apps.progress.models import XPEvent, LessonProgress, UserBadge, StreakProfile
from apps.content.models import Lesson
from apps.progress.services.insights_engine import InsightsEngine

class WeeklyDigestService:
    @classmethod
    def get_cached_leaderboard(cls):
        from django.core.cache import cache
        leaderboard = cache.get('weekly_digest_leaderboard')
        if not leaderboard:
            users = User.objects.filter(is_active=True).annotate(
                total_xp=Sum('xp_events__xp_delta')
            ).order_by('-total_xp')
            leaderboard = {u.id: rank for rank, u in enumerate(users, start=1)}
            cache.set('weekly_digest_leaderboard', leaderboard, 60*60)
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
            user=user, 
            updated_at__gte=one_week_ago,
            completed=True
        ).count()

        # 3. Quizzes and Challenges
        quiz_challenge_count = xp_events.filter(source_type__in=["exercise", "quiz", "challenge"]).count()

        # 4. Current Streak
        streak = StreakProfile.objects.filter(user=user).first()
        current_streak = streak.current_streak if streak else 0

        # 5. Newly unlocked badges
        badges_earned = UserBadge.objects.filter(user=user, earned_at__gte=one_week_ago).select_related('badge')
        badge_names = [ub.badge.name for ub in badges_earned]

        # 6. Leaderboard / Total XP
        user_total_xp = XPEvent.objects.filter(user=user).aggregate(total=Sum("xp_delta"))["total"] or 0
        
        # Calculate Rank (Optimized via global cache)
        leaderboard = cls.get_cached_leaderboard()
        rank = leaderboard.get(user.id, User.objects.count())

        # 7. Recommendations
        completed_lesson_ids = LessonProgress.objects.filter(user=user, completed=True).values_list('lesson_id', flat=True)
        recommended_lessons = Lesson.objects.exclude(id__in=completed_lesson_ids).order_by('order')[:3]
        recommendations = [lesson.title for lesson in recommended_lessons]

        # 8. Newly Released Content
        # Since Lesson doesn't have created_at, we use highest IDs as a proxy for newest content
        new_lessons = Lesson.objects.all().order_by('-id')[:4]
        new_content = [lesson.title for lesson in new_lessons]

        # 9. Advanced Insights
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
            "badges_earned": badge_names,
            "recommendations": recommendations,
            "new_content": new_content,
            "insights": insights,
            "start_date": one_week_ago.strftime("%B %d, %Y"),
            "end_date": now.strftime("%B %d, %Y"),
        }
