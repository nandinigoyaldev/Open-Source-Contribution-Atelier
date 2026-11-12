"""DRF views for the Learning Journal app."""

from __future__ import annotations

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import generics, permissions, status, views
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from .models import (
    JournalComment,
    JournalEntry,
    JournalReaction,
    JournalTemplate,
    ReflectionPrompt,
    UserReflectionStreak,
    WeeklyReflection,
)
from .serializers import (
    JournalCommentSerializer,
    JournalEntrySerializer,
    JournalReactionSerializer,
    JournalStatsSerializer,
    JournalTemplateSerializer,
    PromptResponseSerializer,
    ReflectionPromptSerializer,
    SocialFeedSerializer,
    StreakResponseSerializer,
    UserReflectionStreakSerializer,
    WeeklyReflectionSerializer,
    WeeklySummaryResponseSerializer,
)
from .services import (
    compute_journal_streak,
    generate_weekly_summary,
    get_journal_stats,
    get_reflection_prompt,
    get_social_feed,
)

# ---------------------------------------------------------------------------
#  Journal Entries CRUD
# ---------------------------------------------------------------------------


class JournalEntryListCreateView(generics.ListCreateAPIView):
    """List or create journal entries."""

    serializer_class = JournalEntrySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return JournalEntry.objects.filter(
            user=self.request.user,
        ).order_by("-date", "-created_at")

    def create(self, request, *args, **kwargs):
        client_id = request.data.get("client_id")
        if client_id:
            existing = JournalEntry.objects.filter(
                user=request.user, client_id=client_id
            ).first()
            if existing:
                serializer = self.get_serializer(existing)
                return Response(serializer.data, status=status.HTTP_200_OK)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        entry = serializer.save(user=self.request.user)
        # Award XP based on word count
        xp = min(50, max(5, entry.word_count // 10))
        entry.xp_earned = xp
        entry.save(update_fields=["xp_earned"])

        # Update streak
        compute_journal_streak(self.request.user)


class JournalEntryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a journal entry."""

    serializer_class = JournalEntrySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return JournalEntry.objects.filter(user=self.request.user)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        expected_version = request.data.get("expected_version") or request.data.get(
            "version"
        )
        if expected_version is not None and int(expected_version) != instance.version:
            return Response(
                {
                    "error": "conflict",
                    "message": "Journal entry has been modified by another device or session.",
                    "conflict_type": "version_mismatch",
                    "server_version": instance.version,
                    "server_data": self.get_serializer(instance).data,
                    "server_updated_at": instance.updated_at.isoformat(),
                },
                status=status.HTTP_409_CONFLICT,
            )
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        instance.version += 1
        self.perform_update(serializer)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
#  Today's Entry
# ---------------------------------------------------------------------------


class TodayEntryView(views.APIView):
    """Get or create today's journal entry."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        today = timezone.now().date()
        entry = JournalEntry.objects.filter(
            user=request.user,
            date=today,
        ).first()

        if entry:
            return Response(JournalEntrySerializer(entry).data)

        # Check for a prompt
        prompt = get_reflection_prompt(request.user)

        return Response(
            {
                "exists": False,
                "date": today.isoformat(),
                "prompt": prompt,
            }
        )

    def post(self, request):
        today = timezone.now().date()
        existing = JournalEntry.objects.filter(
            user=request.user,
            date=today,
        ).first()

        if existing:
            return Response(
                {"error": "Entry already exists for today. Use PUT to update."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = request.data.copy()
        data["date"] = today.isoformat()
        serializer = JournalEntrySerializer(data=data)
        serializer.is_valid(raise_exception=True)
        entry = serializer.save(user=request.user)

        # Award XP
        xp = min(50, max(5, entry.word_count // 10))
        entry.xp_earned = xp
        entry.save(update_fields=["xp_earned"])

        compute_journal_streak(request.user)

        return Response(
            JournalEntrySerializer(entry).data,
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
#  Comments
# ---------------------------------------------------------------------------


class JournalCommentListCreateView(generics.ListCreateAPIView):
    """List or add comments to a journal entry."""

    serializer_class = JournalCommentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return JournalComment.objects.filter(
            entry_id=self.kwargs["entry_id"],
        ).select_related("user")

    def perform_create(self, serializer):
        serializer.save(
            user=self.request.user,
            entry_id=self.kwargs["entry_id"],
        )


# ---------------------------------------------------------------------------
#  Reactions
# ---------------------------------------------------------------------------


class JournalReactionView(views.APIView):
    """Toggle a reaction on a journal entry."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, entry_id):
        reaction_type = request.data.get("reaction_type")
        if not reaction_type:
            return Response(
                {"error": "reaction_type is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reaction, created = JournalReaction.objects.get_or_create(
            entry_id=entry_id,
            user=request.user,
            reaction_type=reaction_type,
        )

        if not created:
            reaction.delete()
            return Response({"removed": True})

        return Response(
            {"added": True, "reaction_type": reaction_type},
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
#  Streak
# ---------------------------------------------------------------------------


class JournalStreakView(views.APIView):
    """Get your journaling streak."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        streak = compute_journal_streak(request.user)
        return Response(StreakResponseSerializer(streak).data)


# ---------------------------------------------------------------------------
#  Stats
# ---------------------------------------------------------------------------


class JournalStatsView(views.APIView):
    """Get comprehensive journal statistics."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        stats = get_journal_stats(request.user)
        return Response(JournalStatsSerializer(stats).data)


# ---------------------------------------------------------------------------
#  Weekly Summary
# ---------------------------------------------------------------------------


class WeeklySummaryView(views.APIView):
    """Generate or retrieve your weekly reflection summary."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        week_start_str = request.query_params.get("week_start")
        if week_start_str:
            from datetime import date

            try:
                week_start = date.fromisoformat(week_start_str)
            except ValueError:
                return Response(
                    {"error": "Invalid date format."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            today = timezone.now().date()
            week_start = today - timedelta(days=today.weekday())

        summary = generate_weekly_summary(request.user, week_start)
        return Response(WeeklySummaryResponseSerializer(summary).data)


# ---------------------------------------------------------------------------
#  Social Feed
# ---------------------------------------------------------------------------


class JournalSocialFeedView(views.APIView):
    """Get public journal entries from the community."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        limit = int(request.query_params.get("limit", 20))
        limit = max(1, min(50, limit))
        entries = get_social_feed(request.user, limit=limit)
        return Response(
            SocialFeedSerializer({"entries": entries, "count": len(entries)}).data
        )


# ---------------------------------------------------------------------------
#  Prompts
# ---------------------------------------------------------------------------


class ReflectionPromptView(views.APIView):
    """Get a reflection prompt."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        prompt = get_reflection_prompt(request.user)
        return Response(PromptResponseSerializer(prompt).data)


# ---------------------------------------------------------------------------
#  Templates
# ---------------------------------------------------------------------------


class JournalTemplateListCreateView(generics.ListCreateAPIView):
    """List or create journal templates."""

    serializer_class = JournalTemplateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        from django.db.models import Q

        return JournalTemplate.objects.filter(
            Q(created_by=self.request.user) | Q(is_public=True)
        )

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


# ---------------------------------------------------------------------------
#  Weekly Reflections List
# ---------------------------------------------------------------------------


class WeeklyReflectionListView(generics.ListAPIView):
    """List your weekly reflection summaries."""

    serializer_class = WeeklyReflectionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return WeeklyReflection.objects.filter(
            user=self.request.user,
        ).order_by("-week_start")


# Needed for timedelta
from datetime import timedelta
