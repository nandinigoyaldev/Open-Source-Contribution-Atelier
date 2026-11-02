import json
import logging
import os
import uuid  # NEW: Added for cryptographic nonce generation
from datetime import datetime
from datetime import timezone as dt_timezone

from django.contrib.auth import get_user_model

User = get_user_model()
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, Min, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.http import content_disposition_header
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import UserProfile
from apps.content.models import Lesson
from apps.content.serializers import LessonSerializer
from apps.core.permissions import IsMentor
from apps.core.throttling import SlidingWindowAnonThrottle, SlidingWindowScopedThrottle
from apps.core.utils import parse_iso_datetime
from apps.deduplication.idempotency import idempotent
from apps.progress.constants import XP_PER_LEVEL
from apps.progress.models import XPEvent
from apps.progress.services.xp_service import XPService

from .models import UserNote  # ✅ ADD: UserNote model
from .models import (
    Badge,
    Certificate,
    CodeSubmission,
    DailyActivity,
    ExerciseAttempt,
    HelpRequest,
    LessonBookmark,
    LessonProgress,
    QuizAttempt,
    UserBadge,
    WeeklyGoal,
)
from .serializers import (
    BadgeSerializer,
    BulkSyncSerializer,
    CertificateVerificationSerializer,
    DailyProgressSerializer,
    HelpRequestSerializer,
    LessonProgressCreateSerializer,
    LessonProgressSerializer,
    QuizAttemptSerializer,
    WeeklyGoalSerializer,
)
from .services.activity_timeline import (
    TimelineError,
    get_activity_timeline,
    parse_limit,
    parse_types,
)
from .throttles import HelpRequestRateThrottle

logger = logging.getLogger(__name__)


# ============================================================
# ✅ ADD: Notes Export View
# ============================================================


class ExportNotesView(APIView):
    """
    GET /api/progress/notes/export/

    Export all user notes as a single structured Markdown file.
    Supports optional format parameter: ?format=md (default) or ?format=json
    """

    permission_classes = [permissions.IsAuthenticated]
    format_kwarg = None

    def perform_content_negotiation(self, request, force=False):
        renderers = self.get_renderers()
        return (renderers[0], renderers[0].media_type)

    def get(self, request):
        user = request.user
        format_type = request.query_params.get("format", "md").lower()
        limit_param = request.query_params.get("limit")
        start_param = request.query_params.get("start_date")
        end_param = request.query_params.get("end_date")

        if limit_param:
            try:
                limit = int(limit_param)
                if limit <= 0 or limit > 1000:
                    return Response(
                        {
                            "error": "Export limit must be a positive integer up to 1000."
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            except (ValueError, TypeError):
                return Response(
                    {"error": "Invalid limit parameter."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            limit = 1000

        start_date = None
        end_date = None
        if start_param:
            parsed_start = parse_iso_datetime(start_param)
            if parsed_start is None:
                return Response(
                    {"error": "Invalid start_date format. Use YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            start_date = parsed_start.date()

        if end_param:
            parsed_end = parse_iso_datetime(end_param)
            if parsed_end is None:
                return Response(
                    {"error": "Invalid end_date format. Use YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            end_date = parsed_end.date()

        if start_date and end_date:
            if start_date > end_date:
                return Response(
                    {"error": "start_date cannot be after end_date."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if (end_date - start_date).days > 365:
                return Response(
                    {"error": "Date range cannot exceed 1 year (365 days)."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Fetch notes for the user
        notes = (
            UserNote.objects.filter(user=user)
            .select_related("lesson")
            .order_by("lesson__order")
        )

        if start_date:
            notes = notes.filter(created_at__date__gte=start_date)
        if end_date:
            notes = notes.filter(created_at__date__lte=end_date)

        if not notes.exists():
            return Response(
                {"error": "No notes found to export"}, status=status.HTTP_404_NOT_FOUND
            )

        notes = list(notes[:limit])

        if format_type == "json":
            return self._export_json(notes, user)
        else:
            return self._export_markdown(notes, user)

    def _export_markdown(self, notes, user):
        """
        Export notes as a structured Markdown file.
        """
        # Group notes by module
        modules = {}
        for note in notes:
            module_obj = getattr(note.lesson, "module", None)
            module_name = (
                module_obj.title
                if module_obj and hasattr(module_obj, "title")
                else "Uncategorized"
            )
            if module_name not in modules:
                modules[module_name] = {"module": module_obj, "lessons": {}}

            lesson_title = note.lesson.title
            if lesson_title not in modules[module_name]["lessons"]:
                modules[module_name]["lessons"][lesson_title] = []

            modules[module_name]["lessons"][lesson_title].append(note)

        # Build Markdown content
        markdown_lines = []

        # Header
        markdown_lines.append(f"# 📝 Notes Export - {user.username}")
        markdown_lines.append(
            f"**Exported on:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        markdown_lines.append(f"**Total Notes:** {len(notes)}")
        markdown_lines.append("")
        markdown_lines.append("---")
        markdown_lines.append("")

        # Table of Contents
        markdown_lines.append("## 📑 Table of Contents")
        for module_name in modules.keys():
            markdown_lines.append(
                f"- [{module_name}](#{module_name.lower().replace(' ', '-')})"
            )
        markdown_lines.append("")
        markdown_lines.append("---")
        markdown_lines.append("")

        # Notes by module
        for module_name, module_data in modules.items():
            markdown_lines.append(f"## {module_name}")
            markdown_lines.append("")

            for lesson_title, lesson_notes in module_data["lessons"].items():
                markdown_lines.append(f"### 📖 {lesson_title}")
                markdown_lines.append("")

                for note in lesson_notes:
                    # Note metadata
                    markdown_lines.append(f"**Note ID:** {note.id}")
                    markdown_lines.append(
                        f"**Created:** {note.created_at.strftime('%Y-%m-%d %H:%M')}"
                    )
                    if note.updated_at and note.updated_at != note.created_at:
                        markdown_lines.append(
                            f"**Updated:** {note.updated_at.strftime('%Y-%m-%d %H:%M')}"
                        )

                    # Note content with tags
                    if hasattr(note, "tags") and note.tags:
                        markdown_lines.append(f"**Tags:** {', '.join(note.tags)}")

                    markdown_lines.append("")

                    # Note content
                    markdown_lines.append("```")
                    markdown_lines.append(note.content)
                    markdown_lines.append("```")
                    markdown_lines.append("")

                    # Separator between notes in same lesson
                    if len(lesson_notes) > 1:
                        markdown_lines.append("---")
                        markdown_lines.append("")

        # Footer
        markdown_lines.append("---")
        markdown_lines.append(
            f"*Exported from Open Source Contribution Atelier on {datetime.now().strftime('%Y-%m-%d')}*"
        )
        markdown_lines.append("")
        markdown_lines.append("_Happy Learning! 🚀_")

        # Create response
        markdown_content = "\n".join(markdown_lines)
        filename = f"notes_export_{user.username}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

        response = HttpResponse(
            markdown_content, content_type="text/markdown; charset=utf-8"
        )
        response["Content-Disposition"] = content_disposition_header(True, filename)

        return response

    def _export_json(self, notes, user):
        """
        Export notes as JSON.
        """
        data = {
            "username": user.username,
            "email": user.email,
            "exported_at": datetime.now().isoformat(),
            "total_notes": len(notes),
            "notes": [],
        }

        for note in notes:
            module_obj = getattr(note.lesson, "module", None)
            data["notes"].append(
                {
                    "id": note.id,
                    "lesson_title": note.lesson.title,
                    "module_title": (
                        module_obj.title
                        if module_obj and hasattr(module_obj, "title")
                        else None
                    ),
                    "content": note.content,
                    "tags": note.tags if hasattr(note, "tags") else [],
                    "created_at": note.created_at.isoformat(),
                    "updated_at": (
                        note.updated_at.isoformat() if note.updated_at else None
                    ),
                }
            )

        filename = f"notes_export_{user.username}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        json_content = json.dumps(data, indent=2, ensure_ascii=False)

        response = HttpResponse(
            json_content, content_type="application/json; charset=utf-8"
        )
        response["Content-Disposition"] = content_disposition_header(True, filename)

        return response


# ============================================================
# Rest of the views (existing code continues below)
# ============================================================


class BadgePagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


@extend_schema(responses=BadgeSerializer(many=True))
class BadgeListView(ListAPIView):
    serializer_class = BadgeSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = BadgePagination

    def get_queryset(self):
        queryset = Badge.objects.all().order_by("name")
        category = self.request.query_params.get("category")
        if category:
            queryset = queryset.filter(category__iexact=category.strip())
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(name__icontains=search.strip())
        return queryset


@extend_schema_view(
    get=extend_schema(responses=LessonProgressSerializer(many=True)),
    post=extend_schema(
        request=LessonProgressCreateSerializer, responses=LessonProgressSerializer
    ),
)
class MyProgressView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request):
        return self.post(request)

    def get(self, request):
        progress = LessonProgress.objects.filter(
            user=request.user, organization=request.user.organization
        ).select_related("lesson")
        serializer = LessonProgressSerializer(progress, many=True)
        return Response(serializer.data)

    @idempotent
    def post(self, request):
        from apps.content.models import Lesson
        from apps.progress.services.progress_buffer import ProgressBufferService
        from apps.progress.services.progress_tracking_service import (
            ProgressTrackingService,
        )

        lesson_slug = request.data.get("lesson_slug")
        idempotency_key = request.data.get("idempotency_key")
        client_timestamp_ms = request.data.get("client_timestamp")
        base_score = request.data.get("score", 100)
        completed = request.data.get("completed", True)

        try:
            lesson = Lesson.objects.get(
                slug=lesson_slug,
                organization=request.user.organization,
            )
        except Lesson.DoesNotExist:
            return Response(
                {"error": "Lesson not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        payload = {
            "user_id": request.user.id,
            "lesson_slug": lesson_slug,
            "score": base_score,
            "completed": completed,
            "idempotency_key": idempotency_key,
            "client_timestamp": client_timestamp_ms,
        }

        buffered = ProgressBufferService.buffer_update(
            request.user.id, lesson_slug, payload
        )

        if buffered:
            # Return accepted response with optimistic in-memory model
            progress = LessonProgress(
                user=request.user,
                lesson=lesson,
                completed=completed,
                base_score=base_score,
                score=base_score,
            )
            serializer = LessonProgressSerializer(progress)
            return Response(serializer.data, status=status.HTTP_202_ACCEPTED)

        # Fallback to synchronous update if Redis is not available
        progress, created, idempotency_hit = (
            ProgressTrackingService.record_lesson_progress(
                user=request.user,
                lesson_slug=lesson_slug,
                base_score=base_score,
                completed=completed,
                idempotency_key=idempotency_key,
                client_timestamp_ms=client_timestamp_ms,
            )
        )

        serializer = LessonProgressSerializer(progress)

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class BulkSyncProgressView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @idempotent
    def post(self, request):
        serializer = BulkSyncSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from apps.progress.services.progress_tracking_service import (
            ProgressTrackingService,
        )

        synced_ids = ProgressTrackingService.bulk_sync_progress(
            user=request.user, lessons_data=serializer.validated_data["lessons"]
        )

        return Response(
            {"synced_count": len(synced_ids), "progress_ids": synced_ids},
            status=status.HTTP_200_OK,
        )


@extend_schema(
    summary="Bulk update lesson progress",
    description="Updates multiple lesson progress states atomically in a single transaction.",
    request=BulkSyncSerializer,
    responses={
        200: OpenApiResponse(
            description="Successful bulk update summary: {success, transaction_outcome, updated_count, updated_ids, metadata}"
        ),
        400: OpenApiResponse(
            description="Validation failures (duplicate entries, invalid lessons, etc.)"
        ),
        500: OpenApiResponse(description="Transaction failures or internal errors"),
    },
)
class BulkProgressUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = BulkSyncSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "success": False,
                    "transaction_outcome": "failed",
                    "validation_failures": serializer.errors,
                    "updated_count": 0,
                    "updated_ids": [],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        validated_data = serializer.validated_data["lessons"]

        from apps.progress.services.progress_batch_service import (
            DuplicateEntryException,
            InvalidLessonException,
            process_bulk_progress_updates,
        )

        try:
            success_ids = process_bulk_progress_updates(request.user, validated_data)
        except DuplicateEntryException as e:
            return Response(
                {
                    "success": False,
                    "transaction_outcome": "failed",
                    "validation_failures": {"duplicate_entries": e.duplicates},
                    "updated_count": 0,
                    "updated_ids": [],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except InvalidLessonException as e:
            return Response(
                {
                    "success": False,
                    "transaction_outcome": "rolled_back",
                    "validation_failures": {"invalid_lessons": e.missing_slugs},
                    "updated_count": 0,
                    "updated_ids": [],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {
                    "success": False,
                    "transaction_outcome": "rolled_back",
                    "validation_failures": {"exception": str(e)},
                    "updated_count": 0,
                    "updated_ids": [],
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "success": True,
                "transaction_outcome": "committed",
                "validation_failures": {},
                "updated_count": len(success_ids),
                "updated_ids": success_ids,
                "metadata": {
                    "synced_at": request.data.get("metadata", {}).get("timestamp", None)
                },
            },
            status=status.HTTP_200_OK,
        )


class MergedSequence:
    def __init__(self, items, total_count):
        self.items = items
        self.total_count = total_count

    def __len__(self):
        return self.total_count

    def __getitem__(self, key):
        if isinstance(key, slice):
            return self.items[key]
        return self.items[key]


class CommunityFeedPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 50


@extend_schema(
    responses=OpenApiResponse(
        description="Paginated community activity feed combining help requests, code submissions, badges, and lesson completions."
    )
)
class CommunityFeedView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        org_id = (
            UserProfile.objects.filter(user=request.user)
            .values_list("organization_id", flat=True)
            .first()
        )

        if org_id:
            user_ids = UserProfile.objects.filter(
                organization_id=org_id, user__is_active=True
            ).values_list("user_id", flat=True)
        else:
            user_ids = User.objects.filter(is_active=True).values_list("id", flat=True)

        paginator = CommunityFeedPagination()
        page_size = paginator.get_page_size(request) or paginator.page_size

        help_requests_qs = (
            HelpRequest.objects.filter(
                user_id__in=user_ids,
            )
            .select_related("user", "lesson")
            .order_by("-created_at")
        )

        code_submissions_qs = (
            CodeSubmission.objects.filter(
                user_id__in=user_ids,
            )
            .select_related("user", "exercise")
            .order_by("-created_at")
        )

        badges_qs = (
            UserBadge.objects.filter(
                user_id__in=user_ids,
            )
            .select_related("user", "badge")
            .order_by("-earned_at")
        )

        lesson_progress_qs = (
            LessonProgress.objects.filter(
                user_id__in=user_ids,
                completed=True,
            )
            .select_related("user", "lesson")
            .order_by("-updated_at")
        )

        total_count = (
            help_requests_qs.count()
            + code_submissions_qs.count()
            + badges_qs.count()
            + lesson_progress_qs.count()
        )

        raw_page_param = request.query_params.get(paginator.page_query_param, 1)
        if raw_page_param in paginator.last_page_strings:
            import math

            page_number = math.ceil(total_count / page_size) if total_count > 0 else 1
        else:
            try:
                page_number = int(raw_page_param)
                if page_number < 1:
                    page_number = 1
            except (ValueError, TypeError):
                page_number = 1

        offset = (page_number - 1) * page_size
        needed = offset + page_size

        help_requests = help_requests_qs[:needed]
        code_submissions = code_submissions_qs[:needed]
        badges = badges_qs[:needed]
        lesson_progress = lesson_progress_qs[:needed]

        max_length_param = request.query_params.get("max_length")
        max_length = None
        if max_length_param is not None:
            try:
                max_length = int(max_length_param)
                if max_length <= 0:
                    max_length = None
            except (ValueError, TypeError):
                max_length = None

        def format_desc(text: str) -> tuple[str, bool]:
            if not text:
                return "", False
            if max_length is not None and len(text) > max_length:
                return text[:max_length], True
            return text, False

        entries = []

        for hr in help_requests:
            desc, is_trunc = format_desc(hr.message)
            entry_data = {
                "id": f"hr_{hr.id}",
                "type": "help_request",
                "user_id": hr.user_id,
                "username": hr.user.username,
                "title": f"asked for help on {hr.lesson.title}",
                "description": desc,
                "created_at": hr.created_at.isoformat(),
            }
            if max_length is not None:
                entry_data["is_truncated"] = is_trunc
            entries.append(entry_data)

        for cs in code_submissions:
            desc, is_trunc = format_desc(cs.description if cs.description else "")
            entry_data = {
                "id": f"cs_{cs.id}",
                "type": "code_submission",
                "user_id": cs.user_id,
                "username": cs.user.username,
                "title": f"submitted code — {cs.title}",
                "description": desc,
                "created_at": cs.created_at.isoformat(),
            }
            if max_length is not None:
                entry_data["is_truncated"] = is_trunc
            entries.append(entry_data)

        for ub in badges:
            desc, is_trunc = format_desc(
                ub.badge.description if ub.badge.description else ""
            )
            entry_data = {
                "id": f"bd_{ub.id}",
                "type": "badge_earned",
                "user_id": ub.user_id,
                "username": ub.user.username,
                "title": f"earned badge — {ub.badge.name}",
                "description": desc,
                "created_at": ub.earned_at.isoformat(),
            }
            if max_length is not None:
                entry_data["is_truncated"] = is_trunc
            entries.append(entry_data)

        for lp in lesson_progress:
            desc, is_trunc = format_desc(f"Scored {lp.score} points")
            entry_data = {
                "id": f"lp_{lp.id}",
                "type": "lesson_completed",
                "user_id": lp.user_id,
                "username": lp.user.username,
                "title": f"completed lesson — {lp.lesson.title}",
                "description": desc,
                "created_at": lp.updated_at.isoformat(),
            }
            if max_length is not None:
                entry_data["is_truncated"] = is_trunc
            entries.append(entry_data)

        entries.sort(key=lambda e: e["created_at"], reverse=True)

        sequence = MergedSequence(entries, total_count)
        page = paginator.paginate_queryset(sequence, request)
        return paginator.get_paginated_response(page)


@extend_schema(
    responses=OpenApiResponse(
        description="Community stats: active_contributors, merged_prs, response_sla, open_requests"
    )
)
class CommunityStatsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        from django.contrib.auth import get_user_model

        User = get_user_model()

        user = getattr(request, "user", None)
        org = (
            getattr(user, "organization", None)
            if user and user.is_authenticated
            else None
        )

        cache_key = f"community:stats:{org.id}" if org else "community:stats"

        def compute_stats():
            user_count = User.objects.count()

            if org:
                completed_lessons = LessonProgress.objects.filter(
                    organization=org,
                    completed=True,
                ).count()

                open_help_requests = HelpRequest.objects.filter(
                    organization=org,
                    status=HelpRequest.Status.OPEN,
                ).count()
            else:
                completed_lessons = LessonProgress.objects.filter(
                    completed=True,
                ).count()

                open_help_requests = HelpRequest.objects.filter(
                    status=HelpRequest.Status.OPEN,
                ).count()

            active_contributors = 100 + user_count
            merged_prs = 300 + completed_lessons
            return {
                "active_contributors": active_contributors,
                "merged_prs": merged_prs,
                "response_sla": "3.5h",
                "open_requests": open_help_requests,
            }

        from apps.core.cache.coalescing import CoalescingCache

        org_id = org.id if org else "none"
        cache_key = f"community_stats_org_{org_id}"
        stats = CoalescingCache().get_or_set_coalesced(cache_key, 300, compute_stats)

        return Response(stats)


class UserAchievementsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        completed_lessons = LessonProgress.objects.filter(
            user=request.user, completed=True
        ).count()

        exercises_completed = ExerciseAttempt.objects.filter(
            user=request.user, is_correct=True
        ).count()

        help_requests = HelpRequest.objects.filter(user=request.user).count()

        badges = []

        if completed_lessons >= 1:
            badges.append(
                {
                    "name": "First Contribution",
                    "description": "Completed your first lesson",
                }
            )

        if completed_lessons >= 5:
            badges.append(
                {"name": "Consistent Learner", "description": "Completed 5 lessons"}
            )

        if completed_lessons >= 10:
            badges.append(
                {"name": "Knowledge Explorer", "description": "Completed 10 lessons"}
            )

        if exercises_completed >= 5:
            badges.append(
                {"name": "Challenge Solver", "description": "Solved 5 exercises"}
            )

        if help_requests >= 3:
            badges.append(
                {"name": "Community Helper", "description": "Created 3 help requests"}
            )

        return Response({"earned_badges": badges})


@extend_schema_view(
    get=extend_schema(responses=HelpRequestSerializer(many=True)),
    post=extend_schema(request=HelpRequestSerializer, responses=HelpRequestSerializer),
)
class HelpRequestListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_throttles(self):
        if self.request.method == "POST":
            return [HelpRequestRateThrottle()]
        return []

    def get(self, request):
        help_requests = HelpRequest.objects.filter(
            user=request.user,
            organization=request.user.organization,
        ).select_related("lesson")
        serializer = HelpRequestSerializer(help_requests, many=True)
        return Response(serializer.data)

    def post(self, request):
        lesson_slug = request.data.get("lesson_slug")
        message = request.data.get("message", "").strip()

        if not lesson_slug:
            return Response(
                {"error": "lesson_slug is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not message:
            return Response(
                {"error": "message is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            lesson = Lesson.objects.get(
                slug=lesson_slug,
                organization=request.user.organization,
            )
        except Lesson.DoesNotExist:
            return Response(
                {"error": "Lesson not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        help_request = HelpRequest.objects.create(
            user=request.user,
            lesson=lesson,
            message=message,
            organization=request.user.organization,
        )

        serializer = HelpRequestSerializer(help_request)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class MentorHelpRequestListView(ListAPIView):
    serializer_class = HelpRequestSerializer
    permission_classes = [permissions.IsAuthenticated, IsMentor]

    def get_queryset(self):
        assigned = self.request.user.mentor_profile.assigned_lessons.all()
        return (
            HelpRequest.objects.filter(lesson__in=assigned)
            .select_related("user", "lesson")
            .order_by("-created_at")
        )


@extend_schema(
    responses=OpenApiResponse(
        description="Contributor timeline: first_contribution_date, completed_lessons, exercise_attempts, help_requests, contribution_streak"
    )
)
class ContributorTimelineView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        completed_lessons = LessonProgress.objects.filter(
            user=request.user, completed=True
        ).count()

        exercise_attempts = ExerciseAttempt.objects.filter(user=request.user).count()

        help_requests = HelpRequest.objects.filter(user=request.user).count()

        return Response(
            {
                "first_contribution_date": request.user.date_joined.date(),
                "completed_lessons": completed_lessons,
                "exercise_attempts": exercise_attempts,
                "help_requests": help_requests,
                "contribution_streak": completed_lessons,
            }
        )


@extend_schema(
    parameters=[
        OpenApiParameter(
            "type",
            str,
            many=True,
            description=(
                "Only these activity types: lesson_completed, quiz_attempt, "
                "certificate_issued, badge_earned. Repeat the parameter or separate "
                "values with commas. Omit for every type."
            ),
        ),
        OpenApiParameter("limit", int, description="Page size, 1 to 100 (default 20)."),
        OpenApiParameter(
            "cursor", str, description="`next_cursor` from the previous page."
        ),
    ],
    responses={200: OpenApiResponse(description="One page of the user's activity.")},
)
class ActivityTimelineView(APIView):
    """The signed-in learner's own activity, newest first, with keyset pagination.

    See ``apps/progress/services/activity_timeline.py`` for the response shape.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            types = parse_types(request.query_params.getlist("type"))
            limit = parse_limit(request.query_params.get("limit"))
            data = get_activity_timeline(
                request.user,
                types=types,
                limit=limit,
                cursor=request.query_params.get("cursor") or None,
            )
        except TimelineError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(data, status=status.HTTP_200_OK)


# NEW: View to generate the one-time Nonce for Quizzes
class QuizNonceView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        question_id = request.query_params.get("question_id")
        if not question_id:
            return Response(
                {"error": "question_id required"}, status=status.HTTP_400_BAD_REQUEST
            )

        nonce = str(uuid.uuid4())
        # Store in Redis bounded to user AND specific question. TTL = 900s (15 minutes)
        cache_key = f"quiz_nonce_{request.user.id}_{question_id}_{nonce}"
        cache.set(cache_key, True, timeout=900)

        return Response({"nonce": nonce})


@extend_schema_view(
    post=extend_schema(
        description="Create a quiz attempt. Expected JSON fields: question_id, question_text (optional), selected_answer, correct_answer, is_correct, time_taken_seconds.",
        responses=OpenApiResponse(
            description="Created attempt summary: {id, question_id, is_correct, created_at}"
        ),
    ),
    get=extend_schema(
        description="List quiz attempts and stats. Optional query param: question_id. Returns total_attempts, correct, incorrect, accuracy_percent, attempts array.",
        responses=OpenApiResponse(
            description="Quiz attempts summary and attempts array."
        ),
    ),
)
class QuizAttemptView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @idempotent
    def post(self, request):
        # NEW: Validate the cryptographic nonce
        nonce = request.data.get("nonce")
        question_id = request.data.get("question_id")

        if not nonce or not question_id:
            return Response(
                {"error": "Security Error: Nonce and question_id are required."},
                status=status.HTTP_403_FORBIDDEN,
            )

        cache_key = f"quiz_nonce_{request.user.id}_{question_id}_{nonce}"

        # Check if the nonce exists in Redis
        if not cache.get(cache_key):
            return Response(
                {"error": "Invalid or expired session. Replay attack blocked."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # CRITICAL: Invalidate the nonce immediately to prevent double submission
        cache.delete(cache_key)

        # Existing processing logic
        serializer = QuizAttemptSerializer(data=request.data)
        if serializer.is_valid():
            attempt = serializer.save(user=request.user)
            return Response(
                {
                    "id": attempt.id,
                    "question_id": attempt.question_id,
                    "is_correct": attempt.is_correct,
                    "created_at": attempt.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        attempts = QuizAttempt.objects.filter(user=request.user)

        question_id = request.query_params.get("question_id")
        if question_id:
            attempts = attempts.filter(question_id=question_id)

        total = attempts.count()
        correct = attempts.filter(is_correct=True).count()
        incorrect = total - correct

        return Response(
            {
                "total_attempts": total,
                "correct": correct,
                "incorrect": incorrect,
                "accuracy_percent": (
                    round((correct / total) * 100, 1) if total > 0 else 0
                ),
                "attempts": QuizAttemptSerializer(attempts, many=True).data,
            }
        )


class CertificateVerificationThrottle(SlidingWindowAnonThrottle):
    rate = "10/minute"


class CertificateVerifyView(APIView):
    """Public API to verify certificate by hash."""

    permission_classes = []  # Public endpoint

    def get(self, request, hash):
        try:
            certificate = Certificate.objects.get(
                verification_hash=hash, is_active=True
            )
            return Response(
                {
                    "valid": True,
                    "issued_to": certificate.user.username,
                    "issued_at": certificate.created_at,
                    "course": certificate.lesson.title,
                    "certificate_id": certificate.id,
                }
            )
        except Certificate.DoesNotExist:
            return Response(
                {"valid": False, "message": "Certificate not found or invalid"},
                status=status.HTTP_404_NOT_FOUND,
            )


@extend_schema(responses=CertificateVerificationSerializer)
class CertificateVerificationView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [CertificateVerificationThrottle]

    def get(self, request, hash):
        try:
            certificate = Certificate.objects.get(verification_hash=hash)
        except Certificate.DoesNotExist:
            return Response(
                {"is_valid": False, "error": "Certificate not found or invalid hash."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = CertificateVerificationSerializer(certificate)
        if not certificate.is_active:
            return Response(
                {
                    "is_valid": False,
                    "error": "This certificate has been revoked or deactivated.",
                    "certificate": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {"is_valid": True, "certificate": serializer.data},
            status=status.HTTP_200_OK,
        )


class MyCertificateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        certificate = Certificate.objects.filter(user=request.user).first()
        if certificate:
            serializer = CertificateVerificationSerializer(certificate)
            return Response(
                {"has_certificate": True, "certificate": serializer.data},
                status=status.HTTP_200_OK,
            )

        completed_lessons = LessonProgress.objects.filter(
            user=request.user, completed=True
        ).count()
        total_lessons = Lesson.objects.count()

        if total_lessons > 0 and completed_lessons >= total_lessons:
            certificate = Certificate.objects.create(
                user=request.user, course_name="Open Source Contribution Course"
            )
            serializer = CertificateVerificationSerializer(certificate)
            return Response(
                {"has_certificate": True, "certificate": serializer.data},
                status=status.HTTP_201_CREATED,
            )

        return Response(
            {
                "has_certificate": False,
                "detail": "Course requirements not met. Complete all lessons to unlock.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


@extend_schema(responses=LessonSerializer(many=True))
class RecommendationsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        total_lessons_info = Lesson.objects.values("category").annotate(
            total=Count("id"), min_order=Min("order")
        )
        total_map = {
            item["category"]: {"total": item["total"], "min_order": item["min_order"]}
            for item in total_lessons_info
        }

        completed_progress = LessonProgress.objects.filter(user=user, completed=True)
        completed_lessons_per_category = completed_progress.values(
            "lesson__category"
        ).annotate(completed=Count("id"))
        completed_map = {
            item["lesson__category"]: item["completed"]
            for item in completed_lessons_per_category
        }

        category_rates = []
        for category, info in total_map.items():
            completed = completed_map.get(category, 0)
            total = info["total"]
            min_order = info["min_order"]
            rate = completed / total if total > 0 else 0

            if rate < 1.0:
                category_rates.append(
                    {"category": category, "rate": rate, "min_order": min_order}
                )

        if not category_rates:
            return Response([])

        category_rates.sort(key=lambda x: (-x["rate"], x["min_order"]))
        top_category = category_rates[0]["category"]

        completed_lesson_ids = completed_progress.values_list("lesson_id", flat=True)
        recommended_lessons = (
            Lesson.objects.filter(category=top_category)
            .exclude(id__in=completed_lesson_ids)
            .prefetch_related("exercises", "prerequisites")
            .order_by("order")
        )

        serializer = LessonSerializer(recommended_lessons, many=True)
        return Response(serializer.data)


from .models import CodeSubmission, ExerciseAttempt, PeerReview
from .serializers import CodeSubmissionSerializer, PeerReviewSerializer


class CodeSubmissionView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [SlidingWindowScopedThrottle]
    throttle_scope = "sandbox_user"

    def get(self, request):
        submissions = (
            CodeSubmission.objects.filter(status=CodeSubmission.Status.PENDING_REVIEW)
            .exclude(user=request.user)
            .select_related("user")
        )
        serializer = CodeSubmissionSerializer(submissions, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = CodeSubmissionSerializer(data=request.data)
        if serializer.is_valid():
            submission = serializer.save(user=request.user)
            if submission.exercise:
                eligible = (
                    ExerciseAttempt.objects.filter(
                        exercise=submission.exercise, is_correct=True
                    )
                    .values_list("user_id", flat=True)
                    .distinct()
                )
                submission.assigned_reviewers.set(
                    User.objects.filter(id__in=eligible).exclude(id=request.user.id)[:2]
                )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserProgressPDFExportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from apps.progress.services.pdf_report_service import PDFReportGenerator

        generator = PDFReportGenerator(request.user)
        pdf_bytes = generator.generate()

        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="progress_report.pdf"'
        return response


class PeerReviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, submission_id):
        submission = get_object_or_404(CodeSubmission, id=submission_id)

        if submission.user == request.user:
            return Response(
                {"error": "Cannot review your own submission"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not submission.assigned_reviewers.filter(id=request.user.id).exists():
            return Response(
                {"error": "You are not assigned to review this submission"},
                status=status.HTTP_403_FORBIDDEN,
            )

        existing_review = PeerReview.objects.filter(
            submission=submission, reviewer=request.user
        ).first()

        if existing_review:
            serializer = PeerReviewSerializer(
                existing_review, data=request.data, partial=True
            )
            if serializer.is_valid():
                with transaction.atomic():
                    # Update review content cleanly without granting duplicate XP
                    serializer.save(points_earned=0)
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer = PeerReviewSerializer(data=request.data)
        if serializer.is_valid():
            with transaction.atomic():
                review = serializer.save(
                    submission=submission, reviewer=request.user, points_earned=10
                )

                # Ensure XPEvent is only created once per reviewer review submission
                if not XPEvent.objects.filter(
                    user=request.user,
                    source_type="peer_review",
                    source_id=review.id,
                ).exists():
                    XPEvent.objects.create(
                        user=request.user,
                        source_type="peer_review",
                        source_id=review.id,
                        base_points=10,
                        xp_delta=10,
                    )

                review_count = PeerReview.objects.filter(submission=submission).count()
                if review_count >= 2:
                    reviews = list(
                        PeerReview.objects.filter(submission=submission).values_list(
                            "is_approved", flat=True
                        )
                    )
                    if all(reviews):
                        submission.status = CodeSubmission.Status.REVIEWED
                        submission.save(update_fields=["status"])
                        if submission.exercise:
                            ExerciseAttempt.objects.get_or_create(
                                user=submission.user,
                                exercise=submission.exercise,
                                defaults={
                                    "submitted_command": "peer_review_passed",
                                    "is_correct": True,
                                },
                            )
                    elif not all(reviews):
                        submission.status = CodeSubmission.Status.ESCALATED
                        submission.save(update_fields=["status"])
                return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LessonBookmarkView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, slug=None):
        bookmarks = LessonBookmark.objects.filter(user=request.user).select_related(
            "lesson"
        )
        data = [
            {
                "id": b.id,
                "lesson": b.lesson.id,
                "lesson_slug": b.lesson.slug,
                "lesson_title": b.lesson.title,
                "lesson_difficulty": b.lesson.difficulty,
                "lesson_category": getattr(b.lesson, "category", ""),
                "lesson_estimated_minutes": b.lesson.estimated_minutes,
                "lesson_summary": getattr(b.lesson, "summary", ""),
                "created_at": b.created_at.isoformat(),
            }
            for b in bookmarks
        ]
        return Response(data)

    def post(self, request, slug=None):
        lesson = get_object_or_404(Lesson, slug=slug)
        bookmark, created = LessonBookmark.objects.get_or_create(
            user=request.user, lesson=lesson
        )
        return Response(
            {"status": "added"},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request, slug=None):
        bookmark = get_object_or_404(
            LessonBookmark, user=request.user, lesson__slug=slug
        )
        bookmark.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


class ReadingProgressView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        lesson_slug = request.query_params.get("lesson")
        if not lesson_slug:
            return Response(
                {"error": "Lesson slug required"}, status=status.HTTP_400_BAD_REQUEST
            )

        cache_key = f"reading_progress_{request.user.id}_{lesson_slug}"
        progress = cache.get(cache_key, 0)
        return Response({"progress": progress})

    def post(self, request):
        lesson_slug = request.data.get("lesson")
        progress = request.data.get("progress")

        if not lesson_slug or progress is None:
            return Response(
                {"error": "Lesson slug and progress required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cache_key = f"reading_progress_{request.user.id}_{lesson_slug}"
        cache.set(cache_key, progress, timeout=60 * 60 * 24 * 30)

        # Record reading minutes for streak recovery if active
        from apps.progress.services.streak_recovery_service import StreakRecoveryService

        StreakRecoveryService.record_reading_minute(request.user)

        return Response({"status": "success", "progress": progress})


class DailyLessonStatsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        progress_records = (
            LessonProgress.objects.filter(user=request.user, completed=True)
            .select_related("lesson")
            .order_by("updated_at")
        )

        # Group by date locally in Python
        stats = {}
        for record in progress_records:
            date_str = record.updated_at.date().isoformat()
            if date_str not in stats:
                stats[date_str] = {
                    "date": record.updated_at.date(),
                    "count": 0,
                    "lessons": [],
                }
            stats[date_str]["count"] += 1
            stats[date_str]["lessons"].append(record.lesson.title)

        data = sorted(stats.values(), key=lambda x: x["date"])
        serializer = DailyProgressSerializer(data, many=True)
        return Response(serializer.data)


class LeaderboardView(APIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get(self, request):
        time_period = request.query_params.get("time_period", "all_time")
        search_username = request.query_params.get("username", None)
        try:
            page = int(request.query_params.get("page", 1))
            limit = int(request.query_params.get("limit", 50))
        except ValueError:
            page = 1
            limit = 50
        page = max(page, 1)
        limit = min(max(limit, 1), 200)

        from datetime import datetime, timedelta

        from django.contrib.auth import get_user_model
        from django.db.models import (
            Count,
            F,
            IntegerField,
            OuterRef,
            Q,
            Subquery,
            Sum,
            Value,
        )
        from django.db.models.functions import Coalesce

        from apps.challenges.models import ChallengeCompletion
        from apps.core.cache.coalescing import CoalescingCache
        from apps.dashboard.models import Issue, PullRequest
        from apps.progress.models import LessonProgress, Season, StreakProfile

        User = get_user_model()

        # Period start boundary (None means all-time).
        now = timezone.now()
        start_date = None
        if time_period == "all_time":
            start_date = None
        elif time_period == "weekly":
            start_date = (now - timedelta(days=now.weekday())).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        elif time_period == "monthly":
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif time_period == "nsoc" or time_period.startswith("seasonal"):
            season = Season.objects.filter(is_active=True).first()
            if season is not None and season.start_date:
                start_date = timezone.make_aware(
                    datetime.combine(season.start_date, datetime.min.time())
                )
        elif time_period.startswith("cohort_"):
            start_date = None
        else:
            return Response(
                {"error": f"Invalid time_period parameter: '{time_period}'"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Compute XP the same way as the contributor dashboard so leaderboard
        # ranks always match a user's dashboard rank. XPEvent is a gamification
        # ledger that most contribution paths never write, so using it as the
        # source yields an empty leaderboard even with real contributions.
        def ranked_users():
            date_filter = {}
            if start_date is not None:
                date_filter["updated_at__gte"] = start_date

            lesson_progress = (
                LessonProgress.objects.filter(
                    user=OuterRef("pk"), completed=True, **date_filter
                )
                .values("user")
                .annotate(total=Sum("score"))
                .values("total")
            )
            issues_xp = (
                Issue.objects.filter(
                    assigned_to=OuterRef("pk"),
                    status=Issue.Status.SOLVED,
                    **date_filter,
                )
                .values("assigned_to")
                .annotate(total=Sum("points") + Sum("bonus_points"))
                .values("total")
            )
            challenge_xp = (
                ChallengeCompletion.objects.filter(user=OuterRef("pk"))
                .values("user")
                .annotate(total=Sum("bonus_earned"))
                .values("total")
            )
            prs_merged = (
                PullRequest.objects.filter(
                    user=OuterRef("pk"),
                    status=PullRequest.Status.MERGED,
                    **date_filter,
                )
                .values("user")
                .annotate(total=Count("id"))
                .values("total")
            )

            users = (
                User.objects.filter(is_staff=False)
                .annotate(
                    lesson_xp=Coalesce(
                        Subquery(lesson_progress, output_field=IntegerField()),
                        Value(0),
                    ),
                    issues_xp=Coalesce(
                        Subquery(issues_xp, output_field=IntegerField()), Value(0)
                    ),
                    challenge_xp=Coalesce(
                        Subquery(challenge_xp, output_field=IntegerField()),
                        Value(0),
                    ),
                    prs_merged=Coalesce(
                        Subquery(prs_merged, output_field=IntegerField()), Value(0)
                    ),
                )
                .annotate(
                    total_xp=F("lesson_xp") + F("issues_xp") + F("challenge_xp"),
                )
                .order_by("-total_xp", "username")
            )
            if search_username:
                users = users.filter(username__icontains=search_username)
            return users

        def compute_leaderboard():
            users = ranked_users()
            total_users_count = users.count()
            offset = (page - 1) * limit
            page_rows = list(users[offset : offset + limit])

            user_ids = [u.pk for u in page_rows]
            streak_map = dict(
                StreakProfile.objects.filter(user_id__in=user_ids).values_list(
                    "user_id", "current_streak"
                )
            )

            leaderboard = []
            for i, user in enumerate(page_rows):
                rank = offset + i + 1
                leaderboard.append(
                    {
                        "user_id": user.pk,
                        "username": user.username,
                        "rank": rank,
                        "total_xp": user.total_xp,
                        "merged_prs": user.prs_merged,
                        "streak_days": streak_map.get(user.pk, 0),
                        "avatar_url": f"https://github.com/{user.username}.png",
                        "html_url": f"https://github.com/{user.username}",
                        "is_top_3": rank <= 3,
                    }
                )
            return total_users_count, leaderboard

        cache_key = (
            f"leaderboard_hof_{time_period}_p{page}_l{limit}_u"
            f"{search_username or 'none'}"
        )
        total_users, leaderboard = CoalescingCache().get_or_set_coalesced(
            cache_key, 300, compute_leaderboard
        )

        # Personal rank from the same computation so it matches the dashboard.
        personal_rank = None
        if request.user.is_authenticated and not search_username:
            me = ranked_users().filter(pk=request.user.id).first()
            if me is not None:
                better_count = (
                    ranked_users()
                    .filter(
                        Q(total_xp__gt=me.total_xp)
                        | Q(total_xp=me.total_xp, username__lt=me.username)
                    )
                    .count()
                )
                personal_rank = {
                    "rank": better_count + 1,
                    "total_xp": me.total_xp,
                }

        total_pages = (total_users + limit - 1) // limit if total_users > 0 else 1

        return Response(
            {
                "leaderboard": leaderboard,
                "personal_rank": personal_rank,
                "page": page,
                "limit": limit,
                "total_users": total_users,
                "total_pages": total_pages,
            },
            status=status.HTTP_200_OK,
        )


class GitHubLeaderboardView(APIView):
    """Read-only ranking of real contributions to the configured GitHub repo."""

    permission_classes = [permissions.AllowAny]
    cache_timeout = 15 * 60

    def get(self, request):
        repository = os.getenv(
            "GITHUB_LEADERBOARD_REPOSITORY",
            "goyaljiiiiii/Open-Source-Contribution-Atelier",
        )
        cache_key = f"github_leaderboard:{repository}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        try:
            import requests

            headers = {"Accept": "application/vnd.github+json"}
            token = os.getenv("GITHUB_TOKEN")
            if token:
                headers["Authorization"] = f"Bearer {token}"
            response = requests.get(
                f"https://api.github.com/repos/{repository}/contributors",
                params={"per_page": 100, "anon": "false"},
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()
            contributors = response.json()
        except Exception as exc:
            logger.warning("GitHub leaderboard request failed: %s", exc)
            return Response(
                {"detail": "GitHub contribution data is temporarily unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        leaderboard = [
            {
                "rank": index,
                "username": contributor["login"],
                "total_xp": contributor.get("contributions", 0),
                "merged_prs": contributor.get("contributions", 0),
                "streak_days": 0,
                "avatar_url": contributor.get("avatar_url", ""),
                "html_url": contributor.get("html_url", ""),
            }
            for index, contributor in enumerate(contributors, start=1)
            if contributor.get("login")
        ]
        data = {
            "source": "github",
            "repository": repository,
            "leaderboard": leaderboard,
            "total_users": len(leaderboard),
            "page": 1,
            "total_pages": 1,
        }
        cache.set(cache_key, data, self.cache_timeout)
        return Response(data)


class BufferMetricsView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        from apps.progress.services.progress_buffer import ProgressBufferService

        metrics = ProgressBufferService.get_queue_metrics()

        # Calculate some derived metrics
        total_queued = metrics.get("total_queued", 0)
        total_processed = metrics.get("total_processed", 0)

        success_rate = 100.0
        if total_queued > 0:
            success_rate = round((total_processed / total_queued) * 100, 2)

        metrics["success_rate_percent"] = success_rate

        return Response({"success": True, "metrics": metrics})


class HeatmapView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        import datetime
        from collections import defaultdict

        from django.shortcuts import get_object_or_404

        from apps.progress.models import (
            DailyActivity,
            ExerciseAttempt,
            LessonProgress,
            QuizAttempt,
        )

        username = request.query_params.get("username")
        if username:
            user = get_object_or_404(User, username=username)
        else:
            if not request.user.is_authenticated:
                return Response(
                    {"detail": "Authentication credentials were not provided."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            user = request.user

        try:
            today = user.user_profile.local_today
        except Exception:
            today = datetime.date.today()

        start_param = request.query_params.get("start_date")
        end_param = request.query_params.get("end_date")

        if start_param:
            parsed_start = parse_iso_datetime(start_param)
            start_date = (
                parsed_start.date()
                if parsed_start is not None
                else today - datetime.timedelta(days=365)
            )
        else:
            start_date = today - datetime.timedelta(days=365)

        if end_param:
            parsed_end = parse_iso_datetime(end_param)
            end_date = parsed_end.date() if parsed_end is not None else today
        else:
            end_date = today

        activity_type_filter = request.query_params.get("activity_type")

        activity_breakdown = defaultdict(
            lambda: {"reading": 0, "quizzes": 0, "code_submissions": 0}
        )

        # Fetch records
        lessons = LessonProgress.objects.filter(
            user=user,
            completed=True,
            updated_at__date__gte=start_date,
            updated_at__date__lte=end_date,
        )
        for lp in lessons:
            d = lp.updated_at.date().isoformat()
            activity_breakdown[d]["reading"] += 1

        quizzes = QuizAttempt.objects.filter(
            user=user, created_at__date__gte=start_date, created_at__date__lte=end_date
        )
        for qa in quizzes:
            d = qa.created_at.date().isoformat()
            activity_breakdown[d]["quizzes"] += 1

        exercises = ExerciseAttempt.objects.filter(
            user=user, created_at__date__gte=start_date, created_at__date__lte=end_date
        )
        for ea in exercises:
            d = ea.created_at.date().isoformat()
            activity_breakdown[d]["code_submissions"] += 1

        daily_dates = set(
            DailyActivity.objects.filter(
                user=user, date__gte=start_date, date__lte=end_date
            ).values_list("date", flat=True)
        )

        all_dates = set(activity_breakdown.keys()) | {
            d.isoformat() for d in daily_dates
        }

        data = []
        for date_str in sorted(all_dates):
            date_obj = datetime.date.fromisoformat(date_str)
            breakdown = activity_breakdown[date_str]
            reading_cnt = breakdown["reading"]
            quizzes_cnt = breakdown["quizzes"]
            code_sub_cnt = breakdown["code_submissions"]

            if activity_type_filter == "reading":
                count = reading_cnt
            elif activity_type_filter == "quizzes":
                count = quizzes_cnt
            elif activity_type_filter == "code_submissions":
                count = code_sub_cnt
            else:
                total_actions = reading_cnt + quizzes_cnt + code_sub_cnt
                if total_actions > 0:
                    count = total_actions
                elif date_obj in daily_dates:
                    count = 1
                else:
                    count = 0

            if count > 0:
                data.append(
                    {
                        "date": date_str,
                        "count": count,
                        "breakdown": {
                            "reading": reading_cnt,
                            "quizzes": quizzes_cnt,
                            "code_submissions": code_sub_cnt,
                        },
                    }
                )

        return Response(data, status=status.HTTP_200_OK)


XP_BREAKDOWN_CATEGORIES = {
    "lessons": ("Lessons", ["lesson"]),
    "quizzes": ("Quizzes", []),
    "challenges": ("Challenges", ["exercise", "bounty"]),
    "streaks": ("Streaks", []),
    "community": ("Community", ["pr", "issue", "review"]),
}


class XPBreakdownView(APIView):
    """XP earned by the current user, grouped by category.

    Only positive XPEvent rows count as earned XP. Quizzes and streaks have no
    XPEvent source type yet, so they report 0; any other earning source (badges,
    milestones) is returned as "other" so the total still adds up.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        totals = dict(
            XPEvent.objects.filter(user=request.user, xp_delta__gt=0)
            .values_list("source_type")
            .annotate(total=Sum("xp_delta"))
        )
        known = set()
        categories = []
        for key, (label, sources) in XP_BREAKDOWN_CATEGORIES.items():
            known.update(sources)
            categories.append(
                {
                    "key": key,
                    "label": label,
                    "xp": sum(totals.get(s, 0) for s in sources),
                }
            )
        other = sum(xp for source, xp in totals.items() if source not in known)
        if other:
            categories.append({"key": "other", "label": "Other", "xp": other})
        return Response(
            {"total_xp": sum(c["xp"] for c in categories), "categories": categories}
        )


class StreakStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from apps.progress.streak_engine import StreakEngine

        data = StreakEngine.get_streak_data(request.user)

        formatted_data = {
            "current_streak": data["current_streak"],
            "highest_streak": data["longest_streak"],
            "multiplier": data["current_multiplier"],
            "effective_multiplier": data.get(
                "effective_multiplier", data["current_multiplier"]
            ),
            "is_weekend_event": data.get("is_weekend_event", False),
            "next_milestone": (
                data["next_milestone"]["days"] if data["next_milestone"] else None
            ),
        }
        return Response(formatted_data, status=status.HTTP_200_OK)


class StreakRecoveryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from apps.progress.services.streak_recovery_service import StreakRecoveryService

        plan = StreakRecoveryService.get_or_create_recovery_plan(request.user)
        if not plan:
            return Response({"has_recovery_plan": False}, status=status.HTTP_200_OK)

        return Response(
            {
                "has_recovery_plan": True,
                "recovery_plan": {
                    "target_date": plan.target_date.isoformat(),
                    "previous_streak": plan.previous_streak,
                    "quiz_target": plan.quiz_target,
                    "quiz_progress": plan.quiz_progress,
                    "reading_target": plan.reading_target,
                    "reading_progress": plan.reading_progress,
                    "code_target": plan.code_target,
                    "code_progress": plan.code_progress,
                    "is_completed": plan.is_completed,
                },
            },
            status=status.HTTP_200_OK,
        )


class Echo:
    """An object that implements just the write method of the file-like interface."""

    def write(self, value):
        """Write the value by returning it, instead of storing in a buffer."""
        return value


class HeatmapCSVExportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        import csv
        import datetime
        from collections import defaultdict

        from django.http import StreamingHttpResponse

        from apps.progress.models import (
            DailyActivity,
            ExerciseAttempt,
            LessonProgress,
            QuizAttempt,
        )

        user = request.user

        start_param = request.query_params.get("start_date")
        end_param = request.query_params.get("end_date")
        activity_type_filter = request.query_params.get("activity_type")

        try:
            today = user.user_profile.local_today
        except Exception:
            today = datetime.date.today()

        if start_param:
            parsed_start = parse_iso_datetime(start_param)
            if parsed_start is None:
                return Response(
                    {"error": "Invalid start_date format. Use YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            start_date = parsed_start.date()
        else:
            start_date = today - datetime.timedelta(days=365)

        if end_param:
            parsed_end = parse_iso_datetime(end_param)
            if parsed_end is None:
                return Response(
                    {"error": "Invalid end_date format. Use YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            end_date = parsed_end.date()
        else:
            end_date = today

        if start_date > end_date:
            return Response(
                {"error": "start_date cannot be after end_date."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if (end_date - start_date).days > 365:
            return Response(
                {"error": "Date range cannot exceed 1 year (365 days)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        activity_breakdown = defaultdict(
            lambda: {"reading": 0, "quizzes": 0, "code_submissions": 0}
        )

        lessons = LessonProgress.objects.filter(
            user=user,
            completed=True,
            updated_at__date__gte=start_date,
            updated_at__date__lte=end_date,
        )
        for lp in lessons:
            d = lp.updated_at.date().isoformat()
            activity_breakdown[d]["reading"] += 1

        quizzes = QuizAttempt.objects.filter(
            user=user, created_at__date__gte=start_date, created_at__date__lte=end_date
        )
        for qa in quizzes:
            d = qa.created_at.date().isoformat()
            activity_breakdown[d]["quizzes"] += 1

        exercises = ExerciseAttempt.objects.filter(
            user=user, created_at__date__gte=start_date, created_at__date__lte=end_date
        )
        for ea in exercises:
            d = ea.created_at.date().isoformat()
            activity_breakdown[d]["code_submissions"] += 1

        daily_dates = set(
            DailyActivity.objects.filter(
                user=user, date__gte=start_date, date__lte=end_date
            ).values_list("date", flat=True)
        )

        all_dates = set(activity_breakdown.keys()) | {
            d.isoformat() for d in daily_dates
        }

        pseudo_buffer = Echo()
        writer = csv.writer(pseudo_buffer)

        def csv_stream():
            yield writer.writerow(
                [
                    "Date",
                    "Activity Type",
                    "Reading Count",
                    "Quizzes Count",
                    "Code Submissions Count",
                    "Total Count",
                ]
            )

            for date_str in sorted(all_dates):
                date_obj = datetime.date.fromisoformat(date_str)
                breakdown = activity_breakdown[date_str]
                reading_cnt = breakdown["reading"]
                quizzes_cnt = breakdown["quizzes"]
                code_sub_cnt = breakdown["code_submissions"]

                if activity_type_filter == "reading":
                    count = reading_cnt
                    activity_type_label = "Reading"
                elif activity_type_filter == "quizzes":
                    count = quizzes_cnt
                    activity_type_label = "Quizzes"
                elif activity_type_filter == "code_submissions":
                    count = code_sub_cnt
                    activity_type_label = "Code Submissions"
                else:
                    total_actions = reading_cnt + quizzes_cnt + code_sub_cnt
                    if total_actions > 0:
                        count = total_actions
                    elif date_obj in daily_dates:
                        count = 1
                    else:
                        count = 0
                    activity_type_label = "All Activities"

                if count > 0:
                    yield writer.writerow(
                        [
                            date_str,
                            activity_type_label,
                            reading_cnt,
                            quizzes_cnt,
                            code_sub_cnt,
                            count,
                        ]
                    )

        filename = f"activity_export_{start_date}_to_{end_date}.csv"
        response = StreamingHttpResponse(csv_stream(), content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        return response


class WeeklyGoalView(APIView):
    """
    GET /api/progress/weekly-goal/
    PUT /api/progress/weekly-goal/

    View and update current weekly learning goal targets and progress metrics.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        goal = WeeklyGoal.get_or_create_current(user)

        today = timezone.now().date()
        week_start = goal.week_start_date
        week_end = week_start + timezone.timedelta(days=6)

        # Completed lessons this week
        completed_lessons = LessonProgress.objects.filter(
            user=user,
            completed=True,
            updated_at__date__gte=week_start,
            updated_at__date__lte=week_end,
        ).count()

        # XP earned this week
        earned_xp = (
            XPEvent.objects.filter(
                user=user,
                created_at__date__gte=week_start,
                created_at__date__lte=week_end,
            ).aggregate(total=Sum("xp_delta"))["total"]
            or 0
        )

        # Active learning days and estimated learning time (30 mins per active day)
        activity_dates = set(
            DailyActivity.objects.filter(
                user=user,
                date__gte=week_start,
                date__lte=week_end,
            ).values_list("date", flat=True)
        )
        minutes_spent = max(len(activity_dates) * 30, completed_lessons * 15)

        # Calculate percentages
        lessons_pct = (
            min(100, int((completed_lessons / goal.target_lessons) * 100))
            if goal.target_lessons > 0
            else 0
        )
        xp_pct = (
            min(100, int((earned_xp / goal.target_xp) * 100))
            if goal.target_xp > 0
            else 0
        )
        minutes_pct = (
            min(100, int((minutes_spent / goal.target_minutes) * 100))
            if goal.target_minutes > 0
            else 0
        )
        overall_pct = min(100, int((lessons_pct + xp_pct + minutes_pct) / 3))

        days_of_week = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        daily_breakdown = []
        for i in range(7):
            d = week_start + timezone.timedelta(days=i)
            daily_breakdown.append(
                {
                    "day_name": days_of_week[i],
                    "date": d.isoformat(),
                    "is_active": d in activity_dates,
                    "is_today": d == today,
                    "is_future": d > today,
                }
            )

        serializer = WeeklyGoalSerializer(goal)
        data = serializer.data
        data.update(
            {
                "week_end_date": week_end.isoformat(),
                "completed_lessons": completed_lessons,
                "earned_xp": earned_xp,
                "minutes_spent": minutes_spent,
                "lessons_progress_pct": lessons_pct,
                "xp_progress_pct": xp_pct,
                "minutes_progress_pct": minutes_pct,
                "overall_progress_pct": overall_pct,
                "daily_breakdown": daily_breakdown,
            }
        )
        return Response(data)

    def put(self, request):
        user = request.user
        goal = WeeklyGoal.get_or_create_current(user)
        serializer = WeeklyGoalSerializer(goal, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return self.get(request)


class ClaimMultiTierRewardView(APIView):
    """
    POST /api/progress/rewards/claim/

    Claims all reward tiers for a completed multi-stage challenge in a
    single atomic transaction.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        tiers = request.data.get("tiers", [])
        if not isinstance(tiers, list) or not tiers:
            raise ValidationError("`tiers` must be a non-empty list.")

        result = XPService.claim_multi_tier_rewards(request.user, tiers)
        return Response(
            {
                "success": True,
                "xp_events_awarded": len(result["xp_events"]),
                "badges_awarded": len(result["badges"]),
            },
            status=status.HTTP_201_CREATED,
        )
