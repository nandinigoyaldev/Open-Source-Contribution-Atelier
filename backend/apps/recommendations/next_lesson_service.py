from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from django.utils import timezone

from apps.content.models import Lesson
from apps.progress.models import LessonProgress


@dataclass(frozen=True)
class NextLessonCandidateScore:
    lesson: Lesson
    score: float
    why: Dict[str, Any]


class NextLessonRecommendationService:
    """Scores lessons for a personalized "next lesson" pick.

    Scoring is intentionally simple + explainable:
    - prerequisite gap (mandatory): fewer missing prerequisites => higher score
    - streak fit: keep streak alive + avoid overwhelming difficulty when streak is low
    - XP/multiplier fit (best-effort): uses completed lesson scores as an XP proxy
    - recency: prefer lessons never seen before / least recently updated

    The response includes the breakdown so frontend can show a "why recommended" tooltip.
    """

    def __init__(self, user):
        self.user = user

    def get_next_lesson(self) -> Optional[Tuple[Lesson, Dict[str, Any]]]:
        lessons = self._get_candidate_lessons()
        if not lessons:
            return None

        # Include organization scoping via _get_candidate_lessons()
        user_progress = LessonProgress.objects.filter(user=self.user).select_related(
            "lesson"
        )
        progress_by_lesson_id: Dict[int, LessonProgress] = {
            p.lesson_id: p for p in user_progress
        }

        candidates: List[NextLessonCandidateScore] = [
            self._score_lesson(lesson, progress_by_lesson_id) for lesson in lessons
        ]

        best = sorted(candidates, key=lambda c: c.score, reverse=True)[0]
        return best.lesson, best.why

    def _get_candidate_lessons(self) -> List[Lesson]:
        org = getattr(self.user, "organization", None)
        qs = Lesson.objects.all().prefetch_related("prerequisites")
        if org is not None:
            qs = qs.filter(organization=org)

        completed_lesson_ids = LessonProgress.objects.filter(
            user=self.user, completed=True
        ).values_list("lesson_id", flat=True)

        qs = qs.exclude(id__in=list(completed_lesson_ids))
        return list(qs.order_by("order"))

    def _score_lesson(
        self, lesson: Lesson, progress_by_lesson_id: Dict[int, LessonProgress]
    ) -> NextLessonCandidateScore:
        prereq_ids = list(lesson.prerequisites.values_list("id", flat=True))
        completed_prereq_ids = [
            pid
            for pid in prereq_ids
            if pid in progress_by_lesson_id and progress_by_lesson_id[pid].completed
        ]

        total_prereqs = len(prereq_ids)
        completed_prereqs = len(completed_prereq_ids)
        prerequisite_gap = max(0, total_prereqs - completed_prereqs)

        # 1) prerequisite score (primary)
        if total_prereqs == 0:
            prereq_score = 40.0
            prereq_detail = "No prerequisites"
        else:
            prereq_score = 40.0 * (1.0 - (prerequisite_gap / total_prereqs))
            prereq_detail = (
                f"Missing {prerequisite_gap} of {total_prereqs} prerequisite(s)"
            )

        # 2) streak fit
        streak_profile = getattr(self.user, "streak_profile", None)
        current_streak = streak_profile.current_streak if streak_profile else 0
        today = timezone.localdate()
        did_activity_today = LessonProgress.objects.filter(
            user=self.user,
            completed=True,
            updated_at__date=today,
        ).exists()

        if not did_activity_today:
            streak_score = 25.0
            streak_detail = "Keep your streak alive today"
        else:
            streak_score = 15.0 + min(20.0, current_streak * 1.2)
            streak_detail = "Streak-based continuation"

        # 3) XP/multiplier/difficulty fit (best-effort)
        difficulty_map = {"beginner": 0, "intermediate": 1, "advanced": 2}
        lesson_diff = difficulty_map.get((lesson.difficulty or "beginner").lower(), 0)

        completed_scores = list(
            LessonProgress.objects.filter(user=self.user, completed=True).values_list(
                "score", flat=True
            )
        )
        avg_score = (
            (sum(completed_scores) / len(completed_scores)) if completed_scores else 0
        )

        user_level_band = 0
        if avg_score >= 60:
            user_level_band = 1
        if avg_score >= 85:
            user_level_band = 2

        if lesson_diff <= user_level_band:
            xp_score = 20.0
            xp_detail = "Difficulty matches your current XP/level"
        else:
            diff_gap = lesson_diff - user_level_band
            xp_score = max(0.0, 20.0 - diff_gap * 8.0)
            xp_detail = "Lesson is slightly above your current comfort level"

        # 4) recency
        progress = progress_by_lesson_id.get(lesson.id)
        if progress is None:
            recency_score = 10.0
            recency_detail = "New to you"
        else:
            days_since_update = (
                (timezone.now().date() - progress.updated_at.date()).days
                if progress.updated_at
                else 999
            )
            recency_score = max(0.0, 10.0 - min(10, days_since_update))
            recency_detail = f"Last activity {days_since_update} day(s) ago"

        total_score = prereq_score + streak_score + xp_score + recency_score

        # missing prereq titles for explanation
        missing_prereq_titles: List[str] = []
        if prerequisite_gap > 0 and prereq_ids:
            missing_ids = [pid for pid in prereq_ids if pid not in completed_prereq_ids]
            missing_prereq_titles = list(
                Lesson.objects.filter(id__in=missing_ids).values_list(
                    "title", flat=True
                )
            )

        why: Dict[str, Any] = {
            "score": round(total_score, 2),
            "score_breakdown": {
                "prerequisites": round(prereq_score, 2),
                "streak": round(streak_score, 2),
                "xp_difficulty_fit": round(xp_score, 2),
                "recency": round(recency_score, 2),
            },
            "prerequisites": {
                "detail": prereq_detail,
                "missing_titles": missing_prereq_titles[:3],
                "missing_count": prerequisite_gap,
                "total_prerequisites": total_prereqs,
            },
            "streak": {
                "detail": streak_detail,
                "current_streak_days": current_streak,
                "activity_today": did_activity_today,
            },
            "xp_level": {
                "detail": xp_detail,
                "avg_completed_score": round(avg_score, 1) if completed_scores else 0,
                "user_level_band": user_level_band,
                "lesson_difficulty": lesson.difficulty,
            },
            "recency": {"detail": recency_detail},
        }

        return NextLessonCandidateScore(lesson=lesson, score=total_score, why=why)
