from datetime import timedelta

from django.contrib.auth.models import User
from apps.core.cache import multi_level_cache as cache
from django.db import models, transaction
from django.db.models import Count, F, IntegerField, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone
from rest_framework import permissions, serializers, status
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.challenges.models import ChallengeCompletion
from apps.content.models import Lesson
from apps.dashboard.models import Issue, PullRequest
from apps.progress.models import (
    CodeSubmission,
    ExerciseAttempt,
    LessonProgress,
    QuizAttempt,
    XPEvent,
)
from apps.rbac.permissions import HasRole


class LeaderboardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class LeaderboardSerializer(serializers.ModelSerializer):
    prs_merged = serializers.IntegerField(read_only=True)
    issues_solved = serializers.IntegerField(read_only=True)
    xp = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = ("id", "username", "prs_merged", "issues_solved", "xp")


class LeaderboardView(ListAPIView):
    """
    Paginated contributor leaderboard ordered by total XP.
    """

    serializer_class = LeaderboardSerializer
    pagination_class = LeaderboardPagination

    def list(self, request, *args, **kwargs):
        page = request.query_params.get("page", "1")
        cache_key = f"leaderboard_page_{page}"

        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)

        response = super().list(request, *args, **kwargs)
        cache.set(cache_key, response.data, 300)
        return response

    def get_queryset(self):
        timeframe = self.request.query_params.get("timeframe", "all")
        now = timezone.now()
        start_date = None

        if timeframe == "daily":
            start_date = now - timedelta(days=1)
        elif timeframe == "weekly":
            start_date = now - timedelta(days=7)
        elif timeframe == "monthly":
            start_date = now - timedelta(days=30)

        lesson_progress_filter = {"user": OuterRef("pk"), "completed": True}
        issue_filter = {"assigned_to": OuterRef("pk"), "status": Issue.Status.SOLVED}
        pr_filter = {"user": OuterRef("pk"), "status": PullRequest.Status.MERGED}

        if start_date:
            lesson_progress_filter["updated_at__gte"] = start_date
            issue_filter["updated_at__gte"] = start_date
            pr_filter["updated_at__gte"] = start_date

        lesson_progress = (
            LessonProgress.objects.filter(**lesson_progress_filter)
            .values("user")
            .annotate(total=Sum("score"))
            .values("total")
        )

        issues_xp = (
            Issue.objects.filter(**issue_filter)
            .values("assigned_to")
            .annotate(total=Sum("points") + Sum("bonus_points"))
            .values("total")
        )

        challenge_bonus_xp = (
            ChallengeCompletion.objects.filter(user=OuterRef("pk"))
            .values("user")
            .annotate(total=Sum("bonus_earned"))
            .values("total")
        )

        prs_merged = (
            PullRequest.objects.filter(**pr_filter)
            .values("user")
            .annotate(total=Count("id"))
            .values("total")
        )

        issues_solved = (
            Issue.objects.filter(**issue_filter)
            .values("assigned_to")
            .annotate(total=Count("id"))
            .values("total")
        )

        return (
            User.objects.filter(is_staff=False)
            .annotate(
                prs_merged=Coalesce(
                    Subquery(prs_merged, output_field=IntegerField()), Value(0)
                ),
                issues_solved=Coalesce(
                    Subquery(issues_solved, output_field=IntegerField()), Value(0)
                ),
                lesson_xp=Coalesce(
                    Subquery(lesson_progress, output_field=IntegerField()), Value(0)
                ),
                issues_xp=Coalesce(
                    Subquery(issues_xp, output_field=IntegerField()), Value(0)
                ),
                challenge_xp=Coalesce(
                    Subquery(challenge_bonus_xp, output_field=IntegerField()), Value(0)
                ),
            )
            .annotate(
                xp=F("lesson_xp") + F("issues_xp") + F("challenge_xp"),
            )
            .order_by("-xp", "username", "id")
        )


class AdminDashboardView(APIView):
    """
    API view for Admin Dashboard stats.
    Only users with 'Admin' role can access this.
    """

    def get_permissions(self):
        from rest_framework import permissions

        from apps.rbac.permissions import HasAnyRole

        return [permissions.IsAuthenticated(), HasAnyRole(["Admin"])]

    def get(self, request):
        cache_key = "dashboard_admin_stats_v2"
        data = cache.get(cache_key)

        if data is None:
            # 1. Calculate system-wide stats
            total_issues = Issue.objects.count()
            solved_issues = Issue.objects.filter(status=Issue.Status.SOLVED).count()
            open_issues = Issue.objects.filter(status=Issue.Status.OPEN).count()
            in_progress_issues = Issue.objects.filter(
                status=Issue.Status.IN_PROGRESS
            ).count()

            total_prs = PullRequest.objects.count()
            merged_prs = PullRequest.objects.filter(
                status=PullRequest.Status.MERGED
            ).count()
            pending_prs_count = PullRequest.objects.filter(
                status=PullRequest.Status.OPEN
            ).count()
            closed_prs = PullRequest.objects.filter(
                status=PullRequest.Status.CLOSED
            ).count()

            active_contributors = (
                User.objects.filter(is_staff=False)
                .filter(pull_requests__isnull=False)
                .distinct()
                .count()
            )

            system_stats = {
                "total_issues": total_issues,
                "solved_issues": solved_issues,
                "open_issues": open_issues,
                "in_progress_issues": in_progress_issues,
                "total_prs": total_prs,
                "merged_prs": merged_prs,
                "pending_prs": pending_prs_count,
                "closed_prs": closed_prs,
                "active_contributors": active_contributors,
            }

            # 2. Pending PRs queue
            pending_prs_qs = (
                PullRequest.objects.filter(status=PullRequest.Status.OPEN)
                .select_related("user", "issue")
                .order_by("-created_at")
            )

            pending_prs = []
            for pr in pending_prs_qs:
                pending_prs.append(
                    {
                        "id": pr.id,
                        "title": pr.title,
                        "contributor": pr.user.username,
                        "issue_title": pr.issue.title if pr.issue else "No Issue Link",
                        "created_at": pr.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    }
                )

            data = {
                "system_stats": system_stats,
                "pending_prs": pending_prs,
            }

            # Cache for 5 minutes
            cache.set(cache_key, data, 300)

        return Response(data)


class PublicLandingStatsView(APIView):
    """
    Public API view returning summary stats for the landing page.
    No authentication required.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        cache_key = "dashboard_public_landing_stats"
        data = cache.get(cache_key)

        if data is None:
            total_users = User.objects.filter(is_staff=False).count()
            total_lessons_solved = LessonProgress.objects.filter(completed=True).count()
            total_xp = (
                XPEvent.objects.filter(source_type="lesson").aggregate(
                    total=Sum("xp_delta")
                )["total"]
                or 0
            )

            data = {
                "total_users": total_users,
                "total_lessons_solved": total_lessons_solved,
                "total_xp": total_xp,
            }

            # Cache for 5 minutes
            cache.set(cache_key, data, 300)

        return Response(data)


class ContributorDashboardView(APIView):
    """
    API view for Contributor Dashboard stats.
    Accessible to any authenticated user.
    """

    permission_classes = [permissions.IsAuthenticated]

    def _calculate_field(self, user, field):
        if field == "personal_stats":
            issues_solved = Issue.objects.filter(
                assigned_to=user, status=Issue.Status.SOLVED
            ).count()
            prs_merged = PullRequest.objects.filter(
                user=user, status=PullRequest.Status.MERGED
            ).count()

            lesson_xp = (
                LessonProgress.objects.filter(user=user, completed=True).aggregate(
                    total=Sum("score")
                )["total"]
                or 0
            )
            issues_agg = Issue.objects.filter(
                assigned_to=user, status=Issue.Status.SOLVED
            ).aggregate(p_sum=Sum("points"), b_sum=Sum("bonus_points"))
            issues_xp = (issues_agg["p_sum"] or 0) + (issues_agg["b_sum"] or 0)
            challenge_bonus_xp = (
                ChallengeCompletion.objects.filter(user=user).aggregate(
                    total=Sum("bonus_earned")
                )["total"]
                or 0
            )
            total_xp = lesson_xp + issues_xp + challenge_bonus_xp

            # --- NEW CLEAN STREAK LOGIC ---
            from apps.progress.models import StreakProfile

            streak_profile, _ = StreakProfile.objects.get_or_create(user=user)
            streak_days = streak_profile.current_streak
            longest_streak = streak_profile.longest_streak
            # ------------------------------

            # Calculate streak based on unique days of activity (attempts or completed lessons) and active/used freezes
            activity_days = set()
            attempts = ExerciseAttempt.objects.filter(user=user).values_list(
                "created_at", flat=True
            )
            for dt in attempts:
                activity_days.add(timezone.localdate(dt))
            progress_entries = LessonProgress.objects.filter(user=user).values_list(
                "updated_at", flat=True
            )
            for dt in progress_entries:
                activity_days.add(timezone.localdate(dt))

            # Apply streak freezes to calculate streak days
            streak_days = 0
            current_day = today
            while True:
                if current_day < join_date:
                    break
                if current_day in activity_days:
                    streak_days += 1
                elif current_day == today:
                    pass
                else:
                    break
                current_day -= timedelta(days=1)

            # Determine Rank based on user XP vs others
            lesson_xp_sub = (
                LessonProgress.objects.filter(user=OuterRef("pk"), completed=True)
                .values("user")
                .annotate(total=Sum("score"))
                .values("total")
            )
            issues_xp_sub = (
                Issue.objects.filter(
                    assigned_to=OuterRef("pk"), status=Issue.Status.SOLVED
                )
                .values("assigned_to")
                .annotate(total=Sum("points") + Sum("bonus_points"))
                .values("total")
            )
            challenge_xp_sub = (
                ChallengeCompletion.objects.filter(user=OuterRef("pk"))
                .values("user")
                .annotate(total=Sum("bonus_earned"))
                .values("total")
            )

            better_users_count = (
                User.objects.filter(is_staff=False)
                .annotate(
                    u_lxp=Coalesce(
                        Subquery(lesson_xp_sub, output_field=IntegerField()), Value(0)
                    ),
                    u_ixp=Coalesce(
                        Subquery(issues_xp_sub, output_field=IntegerField()), Value(0)
                    ),
                    u_cxp=Coalesce(
                        Subquery(challenge_xp_sub, output_field=IntegerField()),
                        Value(0),
                    ),
                )
                .annotate(
                    user_total_xp=F("u_lxp") + F("u_ixp") + F("u_cxp"),
                )
                .filter(
                    Q(user_total_xp__gt=total_xp)
                    | Q(user_total_xp=total_xp, username__lt=user.username)
                    | Q(user_total_xp=total_xp, username=user.username, id__lt=user.id)
                )
                .count()
            )
            rank = better_users_count + 1

            from apps.progress.models import UserBadge

            earned_badges = list(
                UserBadge.objects.filter(user=user).values_list(
                    "badge__slug", flat=True
                )
            )
            # StreakFreeze has been migrated to StreakProfile.streak_freezes
            spent_points = 0
            available_points = total_xp - spent_points
            unused_freezes_count = getattr(user, "streak_profile", None).streak_freezes if hasattr(user, "streak_profile") else 0

            return {
                "issues_solved": issues_solved,
                "prs_merged": prs_merged,
                "total_xp": total_xp,
                "streak_days": streak_days,
                "longest_streak": longest_streak,  # ADDED THIS TO API
                "rank": rank,
                "earned_badges": earned_badges,
                "available_points": available_points,
                "unused_freezes": unused_freezes_count,
            }

        elif field == "assigned_issues":
            assigned_issues_qs = (
                Issue.objects.filter(assigned_to=user)
                .exclude(status=Issue.Status.SOLVED)
                .order_by("-created_at")
            )

            assigned_issues = []
            for issue in assigned_issues_qs:
                assigned_issues.append(
                    {
                        "id": issue.id,
                        "title": issue.title,
                        "description": issue.description,
                        "status": issue.status,
                        "points": issue.points,
                        "created_at": issue.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    }
                )
            return assigned_issues

        elif field == "recent_prs":
            recent_prs_qs = (
                PullRequest.objects.filter(user=user)
                .select_related("issue")
                .order_by("-created_at")[:10]
            )

            recent_prs = []
            for pr in recent_prs_qs:
                recent_prs.append(
                    {
                        "id": pr.id,
                        "title": pr.title,
                        "status": pr.status,
                        "issue_title": pr.issue.title if pr.issue else "No Issue Link",
                        "created_at": pr.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "merged_at": (
                            pr.merged_at.strftime("%Y-%m-%dT%H:%M:%SZ")
                            if pr.merged_at
                            else None
                        ),
                    }
                )
            return recent_prs

        elif field == "progress_tracker":
            completed_lessons = (
                LessonProgress.objects.select_related("user", "lesson")
                .filter(user=user, completed=True)
                .count()
            )
            total_lessons = Lesson.objects.count()
            completion_percentage = (
                int((completed_lessons / total_lessons) * 100)
                if total_lessons > 0
                else 0
            )

            return {
                "completed_lessons": completed_lessons,
                "total_lessons": total_lessons,
                "completion_percentage": completion_percentage,
            }

        elif field == "active_track":
            from apps.progress.services.milestone_track_service import MilestoneTrackService
            return {
                "active_track_status": MilestoneTrackService.get_user_active_track_status(user),
                "next_milestone": MilestoneTrackService.get_user_next_milestone(user),
            }

    def get(self, request):
        user = request.user
        fields_param = request.query_params.get("fields")
        if fields_param:
            requested_fields = [f.strip() for f in fields_param.split(",") if f.strip()]
        else:
            requested_fields = [
                "personal_stats",
                "assigned_issues",
                "recent_prs",
                "progress_tracker",
                "active_track",
            ]

        data = {}
        for field in requested_fields:
            if field not in [
                "personal_stats",
                "assigned_issues",
                "recent_prs",
                "progress_tracker",
                "active_track",
            ]:
                continue

            cache_key = f"dashboard_contributor_{field}_{user.id}"
            field_data = cache.get(cache_key)
            if field_data is None:
                field_data = self._calculate_field(user, field)
                cache.set(cache_key, field_data, 300)
            data[field] = field_data

        return Response(data)


from drf_spectacular.utils import extend_schema
from rest_framework import status





from django.db import models

from apps.rbac.models import UserRole


class ModeratorAnalyticsView(APIView):
    def get_permissions(self):
        from rest_framework import permissions

        from apps.rbac.permissions import HasAnyRole

        return [permissions.IsAuthenticated(), HasAnyRole(["Admin", "Moderator"])]

    def get(self, request):
        thirty_days_ago = timezone.now() - timedelta(days=30)

        # 1. Registrations
        registrations = (
            User.objects.select_related("profile")
            .filter(date_joined__gte=thirty_days_ago)
            .annotate(date=TruncDate("date_joined"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )

        # 2. Course Enrollments vs Completions
        progress_stats = (
            LessonProgress.objects.filter(updated_at__gte=thirty_days_ago)
            .annotate(date=TruncDate("updated_at"))
            .values("date")
            .annotate(
                completed=Count("id", filter=models.Q(completed=True)),
                enrolled=Count("id"),
            )
            .order_by("date")
        )

        # 3. Quiz Performance
        quiz_stats = (
            QuizAttempt.objects.filter(created_at__gte=thirty_days_ago)
            .values("is_correct")
            .annotate(count=Count("id"))
        )

        # 4. Coding Challenges
        challenge_stats = (
            CodeSubmission.objects.filter(created_at__gte=thirty_days_ago)
            .values("status")
            .annotate(count=Count("id"))
        )

        return Response(
            {
                "registrations": list(registrations),
                "progress_stats": list(progress_stats),
                "quiz_stats": list(quiz_stats),
                "challenge_stats": list(challenge_stats),
            }
        )
