from datetime import timedelta

from apps.challenges.models import ChallengeCompletion
from apps.content.models import Lesson
from apps.dashboard.models import Issue, PullRequest, StreakFreeze
from apps.progress.models import ExerciseAttempt, LessonProgress, QuizAttempt, CodeSubmission
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import (Count, F, IntegerField, OuterRef, Subquery, Sum,
                              Value)
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.db.models.functions import TruncDate
from rest_framework import permissions, serializers
from apps.rbac.permissions import HasRole
from rest_framework.generics import ListAPIView
from rest_framework.pagination import CursorPagination
from rest_framework.response import Response
from rest_framework.views import APIView


class LeaderboardPagination(CursorPagination):
    page_size = 20
    ordering = ("-xp", "username", "id")


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

        lesson_xp = (
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
                    Subquery(lesson_xp, output_field=IntegerField()), Value(0)
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
    Only users with is_staff=True can access this.
    """

    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

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
                LessonProgress.objects.filter(completed=True).aggregate(
                    total=Sum("score")
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

    def get(self, request):
        user = request.user
        cache_key = f"dashboard_contributor_stats_{user.id}"
        data = cache.get(cache_key)

        if data is None:
            # 1. Personal stats
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

            # Calculate streak based on unique days of activity (attempts or completed lessons) and active/used freezes
            activity_days = set()
            attempts = ExerciseAttempt.objects.filter(user=user).values_list(
                "created_at", flat=True
            )
            for dt in attempts:
                activity_days.add(timezone.localdate(dt))
            progress_entries = LessonProgress.objects.filter(
                user=user, completed=True
            ).values_list("updated_at", flat=True)
            for dt in progress_entries:
                activity_days.add(timezone.localdate(dt))

            # Apply streak freezes to calculate streak days
            today = timezone.localdate(timezone.now())
            join_date = timezone.localdate(user.date_joined)
            streak_days = 0
            current_day = today

            with transaction.atomic():
                while True:
                    if current_day < join_date:
                        break

                    if current_day in activity_days:
                        streak_days += 1
                    elif current_day == today:
                        # If today has no activity, we just skip it (does not break the streak and does not count towards it)
                        pass
                    else:
                        # Check if there is already a consumed freeze for this date
                        consumed_freeze = StreakFreeze.objects.filter(
                            user=user, used_on_date=current_day
                        ).exists()
                        if consumed_freeze:
                            streak_days += 1
                        else:
                            # Check if there is an unused freeze to consume
                            unused_freeze = (
                                StreakFreeze.objects.filter(
                                    user=user, used_on_date__isnull=True
                                )
                                .order_by("purchased_at")
                                .first()
                            )
                            if unused_freeze:
                                unused_freeze.used_on_date = current_day
                                unused_freeze.save()
                                streak_days += 1
                            else:
                                # No activity and no freeze available, the streak is broken
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

            all_users = User.objects.filter(is_staff=False).annotate(
                u_lxp=Coalesce(
                    Subquery(lesson_xp_sub, output_field=IntegerField()), Value(0)
                ),
                u_ixp=Coalesce(
                    Subquery(issues_xp_sub, output_field=IntegerField()), Value(0)
                ),
            )

            user_ranks = [(u.id, u.u_lxp + u.u_ixp) for u in all_users]

            user_ranks.sort(key=lambda x: x[1], reverse=True)
            rank = 1
            for index, (uid, u_xp) in enumerate(user_ranks):
                if uid == user.id:
                    rank = index + 1
                    break

            from apps.progress.models import UserBadge

            earned_badges = list(
                UserBadge.objects.filter(user=user).values_list(
                    "badge__slug", flat=True
                )
            )
            spent_points = (
                StreakFreeze.objects.filter(user=user).aggregate(total=Sum("cost"))[
                    "total"
                ]
                or 0
            )
            available_points = total_xp - spent_points
            unused_freezes = StreakFreeze.objects.filter(
                user=user, used_on_date__isnull=True
            ).count()

            personal_stats = {
                "issues_solved": issues_solved,
                "prs_merged": prs_merged,
                "total_xp": total_xp,
                "streak_days": streak_days,
                "rank": rank,
                "earned_badges": earned_badges,
                "available_points": available_points,
                "unused_freezes": unused_freezes,
            }

            # 2. Assigned Issues (Open or In Progress)
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

            # 3. Recent PRs
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

            # 4. Progress tracker
            completed_lessons = LessonProgress.objects.filter(
                user=user, completed=True
            ).count()
            total_lessons = Lesson.objects.count()
            completion_percentage = (
                int((completed_lessons / total_lessons) * 100)
                if total_lessons > 0
                else 0
            )

            progress_tracker = {
                "completed_lessons": completed_lessons,
                "total_lessons": total_lessons,
                "completion_percentage": completion_percentage,
            }

            data = {
                "personal_stats": personal_stats,
                "assigned_issues": assigned_issues,
                "recent_prs": recent_prs,
                "progress_tracker": progress_tracker,
            }

            # Cache for 5 minutes
            cache.set(cache_key, data, 300)

        return Response(data)


from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import status


class BuyStreakFreezeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        responses={
            201: {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "message": {"type": "string"},
                    "available_points": {"type": "integer"},
                },
            }
        }
    )
    def post(self, request):
        user = request.user

        with transaction.atomic():
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
            total_xp = lesson_xp + issues_xp

            spent_points = (
                StreakFreeze.objects.filter(user=user).aggregate(total=Sum("cost"))[
                    "total"
                ]
                or 0
            )
            available_points = total_xp - spent_points

            FREEZE_COST = 100

            if available_points < FREEZE_COST:
                return Response(
                    {
                        "success": False,
                        "message": "Not enough points to buy a streak freeze.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            unused_freezes = StreakFreeze.objects.filter(
                user=user, used_on_date__isnull=True
            ).count()
            if unused_freezes >= 3:
                return Response(
                    {
                        "success": False,
                        "message": "You can only have up to 3 unused streak freezes at a time.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            StreakFreeze.objects.create(user=user, cost=FREEZE_COST)

            # Invalidate cache for dashboard
            cache.delete(f"dashboard_contributor_stats_{user.id}")

            return Response(
                {
                    "success": True,
                    "message": "Streak freeze purchased successfully.",
                    "available_points": available_points - FREEZE_COST,
                },
                status=status.HTTP_201_CREATED,
            )

from django.db import models
from apps.rbac.models import UserRole

class IsModeratorOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser or request.user.is_staff:
            return True
        return UserRole.objects.filter(user=request.user, role__name__in=["Moderator", "Administrator"]).exists()

class ModeratorAnalyticsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsModeratorOrAdmin]

    def get(self, request):
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        # 1. Registrations
        registrations = (
            User.objects.filter(date_joined__gte=thirty_days_ago)
            .annotate(date=TruncDate('date_joined'))
            .values('date')
            .annotate(count=Count('id'))
            .order_by('date')
        )
        
        # 2. Course Enrollments vs Completions
        progress_stats = (
            LessonProgress.objects.filter(updated_at__gte=thirty_days_ago)
            .annotate(date=TruncDate('updated_at'))
            .values('date')
            .annotate(
                completed=Count('id', filter=models.Q(completed=True)),
                enrolled=Count('id')
            )
            .order_by('date')
        )
        
        # 3. Quiz Performance
        quiz_stats = (
            QuizAttempt.objects.filter(created_at__gte=thirty_days_ago)
            .values('is_correct')
            .annotate(count=Count('id'))
        )
        
        # 4. Coding Challenges
        challenge_stats = (
            CodeSubmission.objects.filter(created_at__gte=thirty_days_ago)
            .values('status')
            .annotate(count=Count('id'))
        )

        return Response({
            "registrations": list(registrations),
            "progress_stats": list(progress_stats),
            "quiz_stats": list(quiz_stats),
            "challenge_stats": list(challenge_stats)
        })
