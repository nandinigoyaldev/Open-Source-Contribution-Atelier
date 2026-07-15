import datetime

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.progress.models import (
    Badge,
    ExerciseAttempt,
    LessonProgress,
    Season,
    TrackMilestone,
    UserBadge,
    UserMilestoneCompletion,
    XPEvent,
)


class MilestoneTrackService:
    @staticmethod
    def get_active_season(user) -> Season | None:
        today = timezone.localdate()
        return Season.objects.filter(
            is_active=True, start_date__lte=today, end_date__gte=today
        ).first()

    @staticmethod
    def get_active_season_multiplier(user, activity_type: str) -> float:
        today = timezone.localdate()
        active_season = Season.objects.filter(
            is_active=True, start_date__lte=today, end_date__gte=today
        ).first()
        if active_season and active_season.boost_activity_type == activity_type:
            return active_season.xp_boost_multiplier
        return 1.0

    @staticmethod
    def calculate_progress(user, milestone: TrackMilestone) -> int:
        import datetime as dt_module

        from django.utils.timezone import make_aware

        season = milestone.season
        start_dt = make_aware(
            dt_module.datetime.combine(season.start_date, dt_module.time.min)
        )
        end_dt = make_aware(
            dt_module.datetime.combine(season.end_date, dt_module.time.max)
        )

        if milestone.activity_type == "lesson":
            return LessonProgress.objects.filter(
                user=user, completed=True, updated_at__range=(start_dt, end_dt)
            ).count()

        elif milestone.activity_type == "exercise":
            return ExerciseAttempt.objects.filter(
                user=user, is_correct=True, created_at__range=(start_dt, end_dt)
            ).count()

        elif milestone.activity_type == "xp":
            xp_sum = (
                XPEvent.objects.filter(user=user, created_at__range=(start_dt, end_dt))
                .exclude(source_type__in=["badge", "milestone"])
                .aggregate(total=Sum("xp_delta"))["total"]
            )
            return xp_sum or 0

        return 0

    @staticmethod
    def evaluate_milestones(user):
        from apps.notifications.signals import create_and_push_notification

        today = timezone.localdate()
        active_seasons = Season.objects.filter(
            is_active=True, start_date__lte=today, end_date__gte=today
        )

        for season in active_seasons:
            completed_ids = UserMilestoneCompletion.objects.filter(
                user=user, milestone__season=season
            ).values_list("milestone_id", flat=True)

            incomplete_milestones = season.milestones.exclude(
                id__in=completed_ids
            ).order_by("target_value")

            for milestone in incomplete_milestones:
                progress = MilestoneTrackService.calculate_progress(user, milestone)
                if progress >= milestone.target_value:
                    with transaction.atomic():
                        (
                            completion,
                            created,
                        ) = UserMilestoneCompletion.objects.select_for_update().get_or_create(
                            user=user, milestone=milestone
                        )
                        if created:
                            # Award badge if one is configured
                            if milestone.badge:
                                UserBadge.objects.get_or_create(
                                    user=user, badge=milestone.badge
                                )
                                try:
                                    create_and_push_notification(
                                        recipient=user,
                                        notif_type="badge",
                                        title="🏆 Badge Unlocked!",
                                        message=f"You unlocked milestone badge: {milestone.badge.name}",
                                        meta={
                                            "badge_slug": milestone.badge.slug,
                                            "icon": milestone.badge.icon_asset_url,
                                        },
                                    )
                                except Exception:
                                    pass

                            # Award XP boost if configured
                            if milestone.xp_boost > 0:
                                XPEvent.objects.create(
                                    user=user,
                                    source_type="milestone",
                                    source_id=milestone.id,
                                    base_points=milestone.xp_boost,
                                    multiplier=1.0,
                                    xp_delta=milestone.xp_boost,
                                )

    @staticmethod
    def get_user_active_track_status(user) -> dict | None:
        today = timezone.localdate()
        active_season = Season.objects.filter(
            is_active=True, start_date__lte=today, end_date__gte=today
        ).first()
        if not active_season:
            return None

        completed_ids = UserMilestoneCompletion.objects.filter(
            user=user, milestone__season=active_season
        ).values_list("milestone_id", flat=True)

        milestones = active_season.milestones.all().order_by("target_value")
        completed_count = len(completed_ids)
        total_count = milestones.count()

        return {
            "season_name": active_season.name,
            "season_description": active_season.description,
            "xp_boost_multiplier": active_season.xp_boost_multiplier,
            "boost_activity_type": active_season.boost_activity_type,
            "completed_milestones_count": completed_count,
            "total_milestones_count": total_count,
        }

    @staticmethod
    def get_user_next_milestone(user) -> dict | None:
        today = timezone.localdate()
        active_season = Season.objects.filter(
            is_active=True, start_date__lte=today, end_date__gte=today
        ).first()
        if not active_season:
            return None

        completed_ids = UserMilestoneCompletion.objects.filter(
            user=user, milestone__season=active_season
        ).values_list("milestone_id", flat=True)

        milestones = active_season.milestones.all().order_by("target_value")
        next_milestone = milestones.exclude(id__in=completed_ids).first()

        if not next_milestone:
            return None

        progress = MilestoneTrackService.calculate_progress(user, next_milestone)

        return {
            "id": next_milestone.id,
            "name": next_milestone.name,
            "description": next_milestone.description,
            "activity_type": next_milestone.activity_type,
            "target_value": next_milestone.target_value,
            "current_value": progress,
            "xp_boost": next_milestone.xp_boost,
            "badge_name": next_milestone.badge.name if next_milestone.badge else None,
            "badge_slug": next_milestone.badge.slug if next_milestone.badge else None,
            "badge_icon_url": (
                next_milestone.badge.icon_asset_url if next_milestone.badge else None
            ),
        }

    @staticmethod
    def get_users_active_track_statuses(users) -> dict:
        today = timezone.localdate()
        active_season = Season.objects.filter(
            is_active=True, start_date__lte=today, end_date__gte=today
        ).first()
        if not active_season:
            return {user.id: None for user in users}

        user_ids = [u.id for u in users]

        completions = UserMilestoneCompletion.objects.filter(
            user_id__in=user_ids, milestone__season=active_season
        ).values("user_id", "milestone_id")

        user_completed_counts = {uid: 0 for uid in user_ids}
        for c in completions:
            user_completed_counts[c["user_id"]] += 1

        total_count = active_season.milestones.count()

        return {
            uid: {
                "season_name": active_season.name,
                "season_description": active_season.description,
                "xp_boost_multiplier": active_season.xp_boost_multiplier,
                "boost_activity_type": active_season.boost_activity_type,
                "completed_milestones_count": user_completed_counts[uid],
                "total_milestones_count": total_count,
            }
            for uid in user_ids
        }

    @staticmethod
    def get_users_next_milestones(users) -> dict:
        today = timezone.localdate()
        active_season = Season.objects.filter(
            is_active=True, start_date__lte=today, end_date__gte=today
        ).first()
        if not active_season:
            return {user.id: None for user in users}

        user_ids = [u.id for u in users]

        completions = UserMilestoneCompletion.objects.filter(
            user_id__in=user_ids, milestone__season=active_season
        ).values("user_id", "milestone_id")

        completed_by_user = {uid: set() for uid in user_ids}
        for c in completions:
            completed_by_user[c["user_id"]].add(c["milestone_id"])

        milestones = list(
            active_season.milestones.select_related("badge").order_by("target_value")
        )
        result = {uid: None for uid in user_ids}

        import datetime as dt_module

        from django.db.models import Count
        from django.utils.timezone import make_aware

        start_dt = make_aware(
            dt_module.datetime.combine(active_season.start_date, dt_module.time.min)
        )
        end_dt = make_aware(
            dt_module.datetime.combine(active_season.end_date, dt_module.time.max)
        )

        lesson_progress = dict(
            LessonProgress.objects.filter(
                user_id__in=user_ids,
                completed=True,
                updated_at__range=(start_dt, end_dt),
            )
            .values("user_id")
            .annotate(c=Count("id"))
            .values_list("user_id", "c")
        )

        exercise_progress = dict(
            ExerciseAttempt.objects.filter(
                user_id__in=user_ids,
                is_correct=True,
                created_at__range=(start_dt, end_dt),
            )
            .values("user_id")
            .annotate(c=Count("id"))
            .values_list("user_id", "c")
        )

        xp_progress = dict(
            XPEvent.objects.filter(
                user_id__in=user_ids, created_at__range=(start_dt, end_dt)
            )
            .exclude(source_type__in=["badge", "milestone"])
            .values("user_id")
            .annotate(total=Sum("xp_delta"))
            .values_list("user_id", "total")
        )

        for uid in user_ids:
            next_m = None
            for m in milestones:
                if m.id not in completed_by_user[uid]:
                    next_m = m
                    break

            if not next_m:
                continue

            progress = 0
            if next_m.activity_type == "lesson":
                progress = lesson_progress.get(uid, 0)
            elif next_m.activity_type == "exercise":
                progress = exercise_progress.get(uid, 0)
            elif next_m.activity_type == "xp":
                progress = xp_progress.get(uid, 0)

            result[uid] = {
                "id": next_m.id,
                "name": next_m.name,
                "description": next_m.description,
                "activity_type": next_m.activity_type,
                "target_value": next_m.target_value,
                "current_value": progress or 0,
                "xp_boost": next_m.xp_boost,
                "badge_name": next_m.badge.name if next_m.badge else None,
                "badge_slug": next_m.badge.slug if next_m.badge else None,
                "badge_icon_url": next_m.badge.icon_asset_url if next_m.badge else None,
            }

        return result
