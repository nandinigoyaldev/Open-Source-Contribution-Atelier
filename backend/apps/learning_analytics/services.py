"""
Learning Analytics services.

Contains the core analytics engine that computes user insights,
skill levels, daily metrics, and learning recommendations.
"""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import (
    Avg,
    Case,
    Count,
    F,
    Max,
    Min,
    Q,
    Sum,
    When,
    Window,
)
from django.db.models.functions import TruncDate, TruncWeek
from django.utils import timezone

User = get_user_model()


def _award_step_xp(step):
    """Award XP to the user when a learning path step is completed."""
    from .models import DailyLearningMetric, LearningSession

    if step.xp_reward <= 0:
        return

    user = step.path.user
    today = timezone.now().date()
    start_dt = timezone.make_aware(
        timezone.datetime.combine(today, timezone.datetime.min.time())
    )
    end_dt = start_dt + timedelta(days=1)

    session = LearningSession(
        user=user,
        activity_type=step.activity_type or "lesson",
        activity_id=step.activity_id,
        started_at=start_dt,
        ended_at=end_dt,
        duration_seconds=step.estimated_minutes * 60,
        xp_earned=step.xp_reward,
        completed=True,
        metadata={
            "source": "learning_path",
            "path_id": step.path.id,
            "step_id": step.id,
        },
    )
    session.save()

    # Attach skill tag if present
    if step.skill_tag:
        session.skill_tags.create(
            skill_tag=step.skill_tag,
            confidence=1.0,
        )

    compute_daily_metrics(user, today)


# ---------------------------------------------------------------------------
#  Constants
# ---------------------------------------------------------------------------

# Weights used for the skill-level formula
_WEIGHT_SESSIONS = 0.25
_WEIGHT_XP = 0.35
_WEIGHT_SCORE = 0.30
_WEIGHT_RECENCY = 0.10

# Thresholds for trend detection
_RISING_THRESHOLD = 1.2  # >20% week-over-week increase
_DECLINING_THRESHOLD = 0.8  # >20% decrease


# ---------------------------------------------------------------------------
#  Skill Level Computation
# ---------------------------------------------------------------------------


def compute_skill_level(user, skill_tag) -> dict[str, Any]:
    """Compute the skill level for a single (user, skill_tag) pair via SQL aggregation.

    Returns a dict with: level, total_sessions, total_xp, average_score,
    last_practiced, trend.
    """
    from .models import SessionSkillTag

    now = timezone.now()
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    stats = SessionSkillTag.objects.filter(
        skill_tag=skill_tag,
        session__user=user,
    ).aggregate(
        total_sessions=Count("id"),
        total_xp=Sum("session__xp_earned"),
        avg_score=Avg("session__score"),
        last_practiced=Max("session__started_at"),
        this_week_count=Count(Case(When(session__started_at__gte=week_ago, then=1))),
        last_week_count=Count(
            Case(
                When(
                    session__started_at__gte=two_weeks_ago,
                    session__started_at__lt=week_ago,
                    then=1,
                )
            )
        ),
    )

    total_sessions = stats["total_sessions"] or 0
    if total_sessions == 0:
        return {
            "level": 0,
            "total_sessions": 0,
            "total_xp": 0,
            "average_score": 0.0,
            "last_practiced": None,
            "trend": "stable",
        }

    total_xp = stats["total_xp"] or 0
    avg_score = stats["avg_score"]
    average_score = float(avg_score) if avg_score is not None else 0.0
    last_practiced = stats["last_practiced"]
    this_week_count = stats["this_week_count"] or 0
    last_week_count = stats["last_week_count"] or 0

    # --- Trend: compare this week vs last week ---
    if last_week_count > 0:
        ratio = this_week_count / last_week_count
        if ratio >= _RISING_THRESHOLD:
            trend = "rising"
        elif ratio <= _DECLINING_THRESHOLD:
            trend = "declining"
        else:
            trend = "stable"
    else:
        trend = "rising" if this_week_count > 0 else "stable"

    # --- Normalised component scores (0-100 each) ---
    session_score = min(100, total_sessions * 2)
    xp_score = min(100, total_xp / 5)
    score_comp = average_score

    # Recency: 100 if practised today, decays over 30 days
    days_since = (now - last_practiced).days if last_practiced else 999
    recency_score = max(0, 100 - (days_since * 3.33))

    level = int(
        session_score * _WEIGHT_SESSIONS
        + xp_score * _WEIGHT_XP
        + score_comp * _WEIGHT_SCORE
        + recency_score * _WEIGHT_RECENCY
    )
    level = max(0, min(100, level))

    return {
        "level": level,
        "total_sessions": total_sessions,
        "total_xp": total_xp,
        "average_score": round(average_score, 1),
        "last_practiced": last_practiced,
        "trend": trend,
    }


def compute_all_skill_levels(user) -> list[dict[str, Any]]:
    """Compute skill levels for every skill the user has interacted with in a single grouped SQL query."""
    from .models import SessionSkillTag, SkillTag

    now = timezone.now()
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    aggregated_skills = (
        SessionSkillTag.objects.filter(session__user=user)
        .values("skill_tag")
        .annotate(
            total_sessions=Count("id"),
            total_xp=Sum("session__xp_earned"),
            avg_score=Avg("session__score"),
            last_practiced=Max("session__started_at"),
            this_week_count=Count(
                Case(When(session__started_at__gte=week_ago, then=1))
            ),
            last_week_count=Count(
                Case(
                    When(
                        session__started_at__gte=two_weeks_ago,
                        session__started_at__lt=week_ago,
                        then=1,
                    )
                )
            ),
        )
    )

    if not aggregated_skills:
        return []

    skill_tag_ids = [row["skill_tag"] for row in aggregated_skills]
    skill_tags_by_id = SkillTag.objects.filter(id__in=skill_tag_ids).in_bulk()

    results = []
    for row in aggregated_skills:
        tag_id = row["skill_tag"]
        tag = skill_tags_by_id.get(tag_id)
        if not tag:
            continue

        total_sessions = row["total_sessions"] or 0
        total_xp = row["total_xp"] or 0
        avg_score = row["avg_score"]
        average_score = float(avg_score) if avg_score is not None else 0.0
        last_practiced = row["last_practiced"]
        this_week_count = row["this_week_count"] or 0
        last_week_count = row["last_week_count"] or 0

        # --- Trend: compare this week vs last week ---
        if last_week_count > 0:
            ratio = this_week_count / last_week_count
            if ratio >= _RISING_THRESHOLD:
                trend = "rising"
            elif ratio <= _DECLINING_THRESHOLD:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "rising" if this_week_count > 0 else "stable"

        # --- Normalised component scores (0-100 each) ---
        session_score = min(100, total_sessions * 2)
        xp_score = min(100, total_xp / 5)
        score_comp = average_score

        # Recency: 100 if practised today, decays over 30 days
        days_since = (now - last_practiced).days if last_practiced else 999
        recency_score = max(0, 100 - (days_since * 3.33))

        level = int(
            session_score * _WEIGHT_SESSIONS
            + xp_score * _WEIGHT_XP
            + score_comp * _WEIGHT_SCORE
            + recency_score * _WEIGHT_RECENCY
        )
        level = max(0, min(100, level))

        results.append(
            {
                "skill_tag": tag,
                "level": level,
                "total_sessions": total_sessions,
                "total_xp": total_xp,
                "average_score": round(average_score, 1),
                "last_practiced": last_practiced,
                "trend": trend,
            }
        )

    return sorted(results, key=lambda d: d["level"], reverse=True)


# ---------------------------------------------------------------------------
#  Daily Metrics
# ---------------------------------------------------------------------------


def compute_daily_metrics(user, date=None) -> dict[str, Any]:
    """Compute or refresh daily metrics for *user* on *date*.

    If date is None, it defaults to today.
    Returns the daily metric row data.
    """
    from .models import DailyLearningMetric, LearningSession

    if date is None:
        date = timezone.now().date()

    start_dt = timezone.make_aware(
        timezone.datetime.combine(date, timezone.datetime.min.time())
    )
    end_dt = start_dt + timedelta(days=1)

    sessions = LearningSession.objects.filter(
        user=user,
        started_at__gte=start_dt,
        started_at__lt=end_dt,
    )

    agg = sessions.aggregate(
        total_duration=Sum("duration_seconds"),
        lessons=Count("id", filter=Q(activity_type="lesson")),
        exercises=Count("id", filter=Q(activity_type="exercise")),
        quizzes=Count("id", filter=Q(activity_type="quiz")),
        avg_score=Avg("score", filter=Q(score__isnull=False)),
        total_xp=Sum("xp_earned"),
    )

    total_minutes = (agg["total_duration"] or 0) // 60

    unique_skills = sessions.values("skill_tags__skill_tag_id").distinct().count()

    # Simple focus score heuristic: sessions with score or completed / total
    completed_or_scored = sessions.filter(
        Q(completed=True) | Q(score__isnull=False)
    ).count()
    total = sessions.count()
    focus_score = (completed_or_scored / total) if total > 0 else 0.0

    # Current streak
    from .utils import get_current_streak

    streak_days = get_current_streak(user, up_to=date)

    metric, _ = DailyLearningMetric.objects.update_or_create(
        user=user,
        date=date,
        defaults={
            "total_minutes": total_minutes,
            "lessons_completed": agg["lessons"] or 0,
            "exercises_completed": agg["exercises"] or 0,
            "quizzes_taken": agg["quizzes"] or 0,
            "average_quiz_score": round(agg["avg_score"] or 0, 1),
            "xp_earned": agg["total_xp"] or 0,
            "streak_days": streak_days,
            "unique_skills_practiced": unique_skills,
            "focus_score": round(focus_score, 2),
        },
    )
    return metric


# ---------------------------------------------------------------------------
#  Insight Generation
# ---------------------------------------------------------------------------


def generate_insights(user, force=False) -> list[dict[str, Any]]:
    """Generate fresh learning insights for the user.

    Returns a list of dicts that can be serialised into LearningInsight
    objects.  Existing unread insights of the same type are skipped unless
    *force* is True.
    """
    from .models import LearningInsight

    now = timezone.now()
    insights: list[dict[str, Any]] = []

    # Collect existing unread types to avoid duplicates
    if not force:
        existing_types = set(
            LearningInsight.objects.filter(
                user=user,
                is_read=False,
                is_dismissed=False,
            ).values_list("insight_type", flat=True)
        )
    else:
        existing_types = set()

    # 1. Streak Insight
    streak_data = _generate_streak_insight(user, now)
    if streak_data and streak_data["insight_type"] not in existing_types:
        insights.append(streak_data)

    # 2. Skill Gap Insights
    gaps = _generate_skill_gap_insights(user, now)
    insights.extend(g for g in gaps if g["insight_type"] not in existing_types)

    # 3. Momentum Insight
    momentum = _generate_momentum_insight(user, now)
    if momentum and momentum["insight_type"] not in existing_types:
        insights.append(momentum)

    # 4. Milestone Near
    milestone = _generate_milestone_insight(user, now)
    if milestone and milestone["insight_type"] not in existing_types:
        insights.append(milestone)

    # 5. Learning Tip
    tip = _generate_tip(user, now)
    if tip and tip["insight_type"] not in existing_types:
        insights.append(tip)

    # Bulk-create all new insights
    objs = [LearningInsight(user=user, **data) for data in insights]
    if objs:
        LearningInsight.objects.bulk_create(objs)

    return insights


def _generate_streak_insight(user, now) -> dict[str, Any] | None:
    """Generate streak-related insight."""
    from apps.progress.models import StreakProfile

    try:
        profile = StreakProfile.objects.get(user=user)
    except StreakProfile.DoesNotExist:
        return None

    current = profile.current_streak
    longest = profile.longest_streak

    if current >= 7:
        return {
            "insight_type": "streak",
            "title": f"🔥 {current}-day streak! Keep it going!",
            "body": (
                f"You're on a {current}-day learning streak. "
                f"Your longest was {longest} days. "
                f"You're {max(0, longest - current)} days away from "
                f"your record!"
            ),
            "priority": 2,
            "data": {
                "current_streak": current,
                "longest_streak": longest,
            },
        }
    if current == 0 and longest > 0:
        return {
            "insight_type": "streak",
            "title": "💪 Start a new streak today!",
            "body": (
                f"Your longest streak was {longest} days. "
                f"Complete any activity today to start building "
                f"your comeback!"
            ),
            "priority": 1,
            "data": {"longest_streak": longest},
        }
    if current >= 3 and current < longest:
        remaining = longest - current
        return {
            "insight_type": "streak",
            "title": f"🎯 {remaining} more days to match your record!",
            "body": (
                f"You're at {current} days. Just {remaining} more "
                f"to match your personal best of {longest}!"
            ),
            "priority": 1,
            "data": {
                "current_streak": current,
                "longest_streak": longest,
                "days_to_record": remaining,
            },
        }
    return None


def _generate_skill_gap_insights(user, now) -> list[dict[str, Any]]:
    """Identify skills the user hasn't practised recently."""
    from .models import SkillTag, UserSkillProfile

    profiles = UserSkillProfile.objects.filter(
        user=user,
        level__gte=30,  # Only meaningful skills
    ).select_related("skill_tag")

    insights: list[dict[str, Any]] = []
    stale_threshold = now - timedelta(days=14)

    for profile in profiles:
        if profile.last_practiced and profile.last_practiced < stale_threshold:
            days_since = (now - profile.last_practiced).days
            insights.append(
                {
                    "insight_type": "skill_gap",
                    "title": (
                        f"📖 Revisit {profile.skill_tag.name} " f"(Lv. {profile.level})"
                    ),
                    "body": (
                        f"You haven't practised {profile.skill_tag.name} "
                        f"in {days_since} days. Regular review helps "
                        f"with long-term retention."
                    ),
                    "priority": 1 if days_since > 21 else 0,
                    "action_url": f"/lessons?skill={profile.skill_tag.slug}",
                    "data": {
                        "skill": profile.skill_tag.slug,
                        "days_since_practice": days_since,
                        "current_level": profile.level,
                    },
                }
            )
    return insights


def _generate_momentum_insight(user, now) -> dict[str, Any] | None:
    """Detect significant changes in learning activity."""
    from .models import DailyLearningMetric

    week_ago = (now - timedelta(days=7)).date()
    two_weeks_ago = (now - timedelta(days=14)).date()

    this_week = DailyLearningMetric.objects.filter(
        user=user,
        date__gte=week_ago,
    ).aggregate(total=Sum("total_minutes"), xp=Sum("xp_earned"))

    last_week = DailyLearningMetric.objects.filter(
        user=user,
        date__gte=two_weeks_ago,
        date__lt=week_ago,
    ).aggregate(total=Sum("total_minutes"), xp=Sum("xp_earned"))

    tw_mins = this_week["total"] or 0
    lw_mins = last_week["total"] or 0
    tw_xp = this_week["xp"] or 0
    lw_xp = last_week["xp"] or 0

    if lw_mins == 0 and tw_mins < 60:
        return None

    if lw_mins > 0:
        ratio = tw_mins / lw_mins
        if ratio >= _RISING_THRESHOLD:
            pct = int((ratio - 1) * 100)
            return {
                "insight_type": "momentum",
                "title": f"🚀 Learning momentum up {pct}%!",
                "body": (
                    f"You spent {tw_mins} minutes learning this week "
                    f"(up from {lw_mins} last week). You earned "
                    f"{tw_xp} XP this week — great progress!"
                ),
                "priority": 2,
                "data": {
                    "this_week_minutes": tw_mins,
                    "last_week_minutes": lw_mins,
                    "this_week_xp": tw_xp,
                },
            }
        if ratio <= _DECLINING_THRESHOLD and tw_mins < lw_mins:
            pct = int((1 - ratio) * 100)
            return {
                "insight_type": "momentum",
                "title": f"📉 Learning activity down {pct}%",
                "body": (
                    f"You spent {tw_mins} minutes this week, "
                    f"down from {lw_mins} last week. "
                    f"Even 15 minutes a day makes a difference!"
                ),
                "priority": 1,
                "data": {
                    "this_week_minutes": tw_mins,
                    "last_week_minutes": lw_mins,
                },
            }
    return None


def _generate_milestone_insight(user, now) -> dict[str, Any] | None:
    """Alert users when they are close to completing a learning goal."""
    from .models import LearningGoal

    near_goals = LearningGoal.objects.filter(
        user=user,
        is_completed=False,
        is_archived=False,
        target_value__gt=0,
    ).exclude(
        current_value__gte=F("target_value"),
    )

    for goal in near_goals:
        pct = goal.progress_pct
        if pct >= 80:
            remaining = goal.target_value - goal.current_value
            return {
                "insight_type": "milestone",
                "title": f"🏆 Almost there! {pct}% of '{goal.title}'",
                "body": (
                    f"You're {pct}% of the way to '{goal.title}'. "
                    f"Just {remaining} more to go!"
                ),
                "priority": 2,
                "data": {
                    "goal_id": goal.id,
                    "goal_title": goal.title,
                    "progress_pct": pct,
                    "remaining": remaining,
                },
            }
    return None


def _generate_tip(user, now) -> dict[str, Any] | None:
    """Contextual learning tips based on user's recent activity."""
    from .models import DailyLearningMetric, LearningSession

    recent_sessions = LearningSession.objects.filter(
        user=user,
        started_at__gte=now - timedelta(days=7),
    )

    total = recent_sessions.count()
    quiz_avg = recent_sessions.filter(
        activity_type="quiz", score__isnull=False
    ).aggregate(avg=Avg("score"))["avg"]

    tips = []

    # Tip: diversify activities
    activity_counts = Counter(recent_sessions.values_list("activity_type", flat=True))
    if len(activity_counts) <= 2 and total > 5:
        tips.append(
            {
                "insight_type": "tip",
                "title": "🎯 Try diversifying your activities!",
                "body": (
                    "You've mostly focused on "
                    f"{', '.join(activity_counts.keys())}. "
                    "Mixing exercises, quizzes, and sandbox work "
                    "helps reinforce learning from different angles."
                ),
                "priority": 0,
                "data": {"activities_used": list(activity_counts.keys())},
            }
        )

    # Tip: low quiz score
    if quiz_avg is not None and quiz_avg < 60:
        tips.append(
            {
                "insight_type": "tip",
                "title": "📝 Your quiz scores could use a boost",
                "body": (
                    f"Your average quiz score is {quiz_avg:.0f}%. "
                    "Try re-reading the lesson material and "
                    "revisiting exercises before the next quiz."
                ),
                "priority": 1,
                "data": {"average_quiz_score": quiz_avg},
            }
        )

    # Tip: no activity today
    today = now.date()
    today_activity = DailyLearningMetric.objects.filter(
        user=user,
        date=today,
    ).exists()
    if not today_activity and now.hour >= 18:
        tips.append(
            {
                "insight_type": "tip",
                "title": "⏰ Don't break the streak!",
                "body": (
                    "You haven't logged any activity today. "
                    "Even a quick 10-minute session counts!"
                ),
                "priority": 1,
                "data": {},
            }
        )

    return tips[0] if tips else None


# ---------------------------------------------------------------------------
#  Analytics Dashboard Data
# ---------------------------------------------------------------------------


def get_analytics_dashboard(user, days=30) -> dict[str, Any]:
    """Return a comprehensive analytics dashboard payload."""
    from .models import DailyLearningMetric, LearningSession, SkillTag

    now = timezone.now()
    start_date = (now - timedelta(days=days)).date()

    # --- Time range metrics ---
    metrics = DailyLearningMetric.objects.filter(
        user=user,
        date__gte=start_date,
    ).order_by("date")

    dates = [m.date.isoformat() for m in metrics]
    minutes_per_day = [m.total_minutes for m in metrics]
    xp_per_day = [m.xp_earned for m in metrics]

    total_minutes = sum(minutes_per_day)
    total_xp = sum(xp_per_day)
    total_lessons = sum(m.lessons_completed for m in metrics)
    total_quizzes = sum(m.quizzes_taken for m in metrics)
    avg_focus = sum(m.focus_score for m in metrics) / len(metrics) if metrics else 0.0

    # --- Activity breakdown ---
    sessions = LearningSession.objects.filter(
        user=user,
        started_at__gte=now - timedelta(days=days),
    )
    activity_breakdown = dict(
        sessions.values_list("activity_type")
        .annotate(count=Count("id"))
        .values_list("activity_type", "count")
    )

    # --- Skill levels ---
    from .models import UserSkillProfile

    profiles = list(
        UserSkillProfile.objects.filter(user=user)
        .select_related("skill_tag")
        .order_by("-level")
    )
    if profiles:
        skill_levels_data = [
            {
                "skill": p.skill_tag.name,
                "slug": p.skill_tag.slug,
                "level": p.level,
                "trend": p.trend,
                "average_score": p.average_score,
                "total_sessions": p.total_sessions,
            }
            for p in profiles
        ]
    else:
        skill_levels = compute_all_skill_levels(user)
        skill_levels_data = [
            {
                "skill": s["skill_tag"].name,
                "slug": s["skill_tag"].slug,
                "level": s["level"],
                "trend": s["trend"],
                "average_score": s["average_score"],
                "total_sessions": s["total_sessions"],
            }
            for s in skill_levels
        ]

    # --- Session count heatmap (day of week × hour) ---
    heatmap = _compute_session_heatmap(sessions)

    # --- Goals ---
    from .models import LearningGoal

    active_goals = LearningGoal.objects.filter(
        user=user,
        is_completed=False,
        is_archived=False,
    )
    goals_data = [
        {
            "id": g.id,
            "title": g.title,
            "goal_type": g.goal_type,
            "target": g.target_value,
            "current": g.current_value,
            "progress_pct": g.progress_pct,
            "is_overdue": g.is_overdue,
        }
        for g in active_goals
    ]

    return {
        "period_days": days,
        "summary": {
            "total_minutes": total_minutes,
            "total_xp": total_xp,
            "total_lessons": total_lessons,
            "total_quizzes": total_quizzes,
            "average_focus_score": round(avg_focus, 2),
            "active_days": len(dates),
            "sessions_total": sessions.count(),
        },
        "charts": {
            "dates": dates,
            "minutes_per_day": minutes_per_day,
            "xp_per_day": xp_per_day,
        },
        "activity_breakdown": activity_breakdown,
        "skill_levels": skill_levels_data,
        "heatmap": heatmap,
        "active_goals": goals_data,
    }


def _compute_session_heatmap(sessions) -> list[dict[str, Any]]:
    """Build a day-of-week × hour heatmap from session data."""
    rows = (
        sessions.annotate(date_trunc=TruncDate("started_at"))
        .values("date_trunc")
        .annotate(
            count=Count("id"),
            total_minutes=Sum("duration_seconds"),
        )
        .order_by("date_trunc")
    )
    return [
        {
            "date": row["date_trunc"].isoformat(),
            "sessions": row["count"],
            "minutes": (row["total_minutes"] or 0) // 60,
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
#  Weekly / Monthly Summaries
# ---------------------------------------------------------------------------


def generate_weekly_summary(user) -> dict[str, Any]:
    """Generate a weekly learning summary."""
    from .models import DailyLearningMetric, LearningSession

    now = timezone.now()
    week_start = (now - timedelta(days=now.weekday())).date()
    week_end = week_start + timedelta(days=6)

    metrics = DailyLearningMetric.objects.filter(
        user=user,
        date__gte=week_start,
        date__lte=week_end,
    )

    total_minutes = sum(m.total_minutes for m in metrics)
    total_xp = sum(m.xp_earned for m in metrics)
    total_lessons = sum(m.lessons_completed for m in metrics)
    active_days = metrics.filter(total_minutes__gt=0).count()

    avg_score = metrics.aggregate(avg=Avg("average_quiz_score"))["avg"] or 0

    # Best day
    best_day = metrics.order_by("-xp_earned").first()

    # Skill progress this week
    skill_levels = compute_all_skill_levels(user)
    rising = [s for s in skill_levels if s["trend"] == "rising"]
    declining = [s for s in skill_levels if s["trend"] == "declining"]

    return {
        "period": f"{week_start.isoformat()} to {week_end.isoformat()}",
        "summary": {
            "total_minutes": total_minutes,
            "total_xp": total_xp,
            "total_lessons": total_lessons,
            "active_days": active_days,
            "average_quiz_score": round(avg_score, 1),
        },
        "best_day": (
            {
                "date": best_day.date.isoformat() if best_day else None,
                "xp": best_day.xp_earned if best_day else 0,
            }
            if best_day
            else None
        ),
        "skill_highlights": {
            "rising": [
                {"skill": s["skill_tag"].name, "level": s["level"]} for s in rising[:3]
            ],
            "declining": [
                {"skill": s["skill_tag"].name, "level": s["level"]}
                for s in declining[:3]
            ],
        },
        "recommendations": _weekly_recommendations(
            total_minutes, active_days, avg_score
        ),
    }


def _weekly_recommendations(minutes, active_days, avg_score):
    """Simple rule-based weekly recommendations."""
    recs = []
    if active_days < 4:
        recs.append("Try to study at least 4 days a week for best retention.")
    if minutes < 60:
        recs.append("Aim for 60+ minutes of learning per week for steady progress.")
    if avg_score < 70:
        recs.append("Your quiz scores suggest reviewing lesson material more closely.")
    if not recs:
        recs.append("Great week! Keep the momentum going.")
    return recs


def generate_monthly_recap(user) -> dict[str, Any]:
    """Generate a monthly learning recap."""
    from .models import DailyLearningMetric

    now = timezone.now()
    month_start = now.replace(day=1).date()
    prev_month_end = month_start - timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)

    # Current month
    this_month = DailyLearningMetric.objects.filter(
        user=user,
        date__gte=month_start,
    )
    # Previous month
    last_month = DailyLearningMetric.objects.filter(
        user=user,
        date__gte=prev_month_start,
        date__lte=prev_month_end,
    )

    def _summarize(qs):
        return {
            "total_minutes": sum(m.total_minutes for m in qs),
            "total_xp": sum(m.xp_earned for m in qs),
            "total_lessons": sum(m.lessons_completed for m in qs),
            "total_quizzes": sum(m.quizzes_taken for m in qs),
            "active_days": qs.filter(total_minutes__gt=0).count(),
            "average_focus": round(
                sum(m.focus_score for m in qs) / max(qs.count(), 1), 2
            ),
        }

    this_sum = _summarize(this_month)
    prev_sum = _summarize(last_month)

    # Growth percentages
    def _growth(this_val, prev_val):
        if prev_val == 0:
            return None
        return round((this_val - prev_val) / prev_val * 100, 1)

    return {
        "period": now.strftime("%B %Y"),
        "this_month": this_sum,
        "last_month": prev_sum,
        "growth": {
            "minutes": _growth(this_sum["total_minutes"], prev_sum["total_minutes"]),
            "xp": _growth(this_sum["total_xp"], prev_sum["total_xp"]),
            "lessons": _growth(this_sum["total_lessons"], prev_sum["total_lessons"]),
            "active_days": _growth(this_sum["active_days"], prev_sum["active_days"]),
        },
    }
