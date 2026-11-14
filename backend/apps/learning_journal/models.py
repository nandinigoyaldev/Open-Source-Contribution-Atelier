"""
Learning Journal & Daily Reflection models.

Users write daily reflections about what they learned, track their
learning consistency, productivity, mood, and receive weekly summaries
with insights and reflection prompts.
"""

from __future__ import annotations

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class JournalEntry(models.Model):
    """A single daily learning journal entry."""

    class Mood(models.IntegerChoices):
        TERRIBLE = 1, "😫 Terrible"
        BAD = 2, "😕 Bad"
        OKAY = 3, "😐 Okay"
        GOOD = 4, "😊 Good"
        GREAT = 5, "🤩 Great"

    class Visibility(models.TextChoices):
        PRIVATE = "private", "Private"
        MENTORS = "mentors", "Mentors Only"
        PUBLIC = "public", "Public"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="journal_entries",
    )
    date = models.DateField(
        db_index=True,
        help_text="The calendar date this entry reflects on.",
    )
    title = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional title for the entry.",
    )
    what_i_learned = models.TextField(
        help_text="What did you learn today?",
    )
    challenges_faced = models.TextField(
        blank=True,
        help_text="What was difficult or confusing?",
    )
    key_takeaways = models.TextField(
        blank=True,
        help_text="Key insights or takeaways.",
    )
    tomorrow_goals = models.TextField(
        blank=True,
        help_text="What do you want to learn or accomplish tomorrow?",
    )
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text='Free-form tags, e.g. ["python", "debugging"].',
    )
    mood = models.PositiveSmallIntegerField(
        choices=Mood.choices,
        default=Mood.OKAY,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    productivity_score = models.PositiveSmallIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Self-rated productivity 1-10.",
    )
    hours_spent = models.FloatField(
        default=0.0,
        help_text="Approximate hours spent learning.",
    )
    visibility = models.CharField(
        max_length=10,
        choices=Visibility.choices,
        default=Visibility.PRIVATE,
    )
    linked_lessons = models.JSONField(
        default=list,
        blank=True,
        help_text='Lesson slugs linked to this entry, e.g. ["git-basics"].',
    )
    linked_flashcard_decks = models.JSONField(
        default=list,
        blank=True,
    )
    xp_earned = models.PositiveIntegerField(default=0)
    word_count = models.PositiveIntegerField(default=0)
    version = models.PositiveIntegerField(default=1)
    client_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    is_bookmarked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        unique_together = ("user", "date")
        indexes = [
            models.Index(
                fields=["user", "-date"],
                name="idx_je_user_date",
            ),
            models.Index(
                fields=["user", "mood"],
                name="idx_je_user_mood",
            ),
            models.Index(
                fields=["visibility", "-date"],
                name="idx_je_vis_date",
            ),
        ]

    def __str__(self):
        label = self.title or self.what_i_learned[:50]
        return f"{self.user.username} — {self.date}: {label}"

    def save(self, *args, **kwargs):
        # Auto-compute word count
        text = " ".join(
            filter(
                None,
                [
                    self.what_i_learned,
                    self.challenges_faced,
                    self.key_takeaways,
                    self.tomorrow_goals,
                ],
            )
        )
        self.word_count = len(text.split()) if text else 0
        super().save(*args, **kwargs)


class JournalComment(models.Model):
    """Comments on journal entries (for mentors or peers)."""

    entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="journal_comments",
    )
    content = models.TextField()
    is_mentor_note = models.BooleanField(
        default=False,
        help_text="Comment from a mentor with feedback.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment by {self.user.username} on {self.entry.date}"


class JournalReaction(models.Model):
    """Reactions (likes, encouragement) on journal entries."""

    class ReactionType(models.TextChoices):
        LIKE = "like", "👍 Like"
        ENCOURAGE = "encourage", "💪 Encourage"
        INSIGHTFUL = "insightful", "💡 Insightful"
        CELEBRATE = "celebrate", "🎉 Celebrate"

    entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.CASCADE,
        related_name="reactions",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="journal_reactions",
    )
    reaction_type = models.CharField(
        max_length=15,
        choices=ReactionType.choices,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("entry", "user", "reaction_type")

    def __str__(self):
        return f"{self.user.username} {self.reaction_type} on " f"entry {self.entry_id}"


class ReflectionPrompt(models.Model):
    """Pre-defined or AI-generated reflection prompts."""

    class PromptType(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        CHALLENGE = "challenge", "Challenge"
        MILESTONE = "milestone", "Milestone"

    text = models.TextField()
    prompt_type = models.CharField(
        max_length=10,
        choices=PromptType.choices,
        default=PromptType.DAILY,
    )
    category = models.CharField(
        max_length=50,
        blank=True,
        help_text="Optional category tag for the prompt.",
    )
    is_active = models.BooleanField(default=True)
    times_used = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-times_used"]

    def __str__(self):
        return f"[{self.prompt_type}] {self.text[:60]}"


class UserReflectionStreak(models.Model):
    """Tracks the user's journaling consistency."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="journal_streak",
    )
    current_streak = models.PositiveIntegerField(default=0)
    longest_streak = models.PositiveIntegerField(default=0)
    last_entry_date = models.DateField(null=True, blank=True)
    total_entries = models.PositiveIntegerField(default=0)
    total_words_written = models.PositiveIntegerField(default=0)
    total_hours_reflected = models.FloatField(default=0.0)
    average_mood = models.FloatField(default=0.0)
    average_productivity = models.FloatField(default=0.0)
    favorite_day = models.CharField(
        max_length=10,
        blank=True,
        help_text="Day of week with most entries.",
    )
    favorite_tag = models.CharField(
        max_length=50,
        blank=True,
        help_text="Most frequently used tag.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "User reflection streaks"

    def __str__(self):
        return (
            f"{self.user.username} — "
            f"{self.current_streak} day streak "
            f"({self.total_entries} entries)"
        )

    def recalculate(self):
        from django.db.models import Avg, Sum
        from django.db.models.functions import TruncDate

        entries = JournalEntry.objects.filter(user=self.user)
        agg = entries.aggregate(
            total=Count("id"),
            words=Sum("word_count"),
            hours=Sum("hours_spent"),
            avg_mood=Avg("mood"),
            avg_prod=Avg("productivity_score"),
        )
        self.total_entries = agg["total"] or 0
        self.total_words_written = agg["words"] or 0
        self.total_hours_reflected = round(agg["hours"] or 0, 1)
        self.average_mood = round(agg["avg_mood"] or 0, 1)
        self.average_productivity = round(agg["avg_prod"] or 0, 1)

        # Favorite tag
        all_tags = []
        for t in entries.values_list("tags", flat=True):
            all_tags.extend(t or [])
        if all_tags:
            from collections import Counter

            self.favorite_tag = Counter(all_tags).most_common(1)[0][0]

        self.save()


class WeeklyReflection(models.Model):
    """Auto-generated weekly reflection summary."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="weekly_reflections",
    )
    week_start = models.DateField(
        help_text="Monday of the ISO week.",
    )
    summary = models.TextField(
        help_text="Auto-generated summary of the week's entries.",
    )
    entries_count = models.PositiveIntegerField(default=0)
    total_words = models.PositiveIntegerField(default=0)
    total_hours = models.FloatField(default=0.0)
    average_mood = models.FloatField(default=0.0)
    average_productivity = models.FloatField(default=0.0)
    mood_trend = models.CharField(
        max_length=10,
        choices=[
            ("improving", "Improving"),
            ("stable", "Stable"),
            ("declining", "Declining"),
        ],
        default="stable",
    )
    top_tags = models.JSONField(default=list)
    highlights = models.JSONField(
        default=list,
        help_text="Key highlights from the week's entries.",
    )
    goals_for_next_week = models.TextField(blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "week_start")
        ordering = ["-week_start"]

    def __str__(self):
        return (
            f"Weekly {self.week_start} — "
            f"{self.user.username} "
            f"({self.entries_count} entries)"
        )


class JournalTemplate(models.Model):
    """Reusable journal entry templates."""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="journal_templates",
    )
    is_public = models.BooleanField(default=False)
    sections = models.JSONField(
        default=list,
        help_text=(
            "List of section titles, " 'e.g. ["What I learned", "Challenges", "Goals"].'
        ),
    )
    default_tags = models.JSONField(default=list, blank=True)
    clone_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-clone_count", "name"]

    def __str__(self):
        return self.name


# Needed for recalculate
from django.db.models import Count
