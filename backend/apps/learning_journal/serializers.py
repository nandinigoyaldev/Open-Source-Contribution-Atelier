"""DRF serializers for the Learning Journal app."""

from rest_framework import serializers

from .models import (
    JournalComment,
    JournalEntry,
    JournalReaction,
    JournalTemplate,
    ReflectionPrompt,
    UserReflectionStreak,
    WeeklyReflection,
)


class JournalEntrySerializer(serializers.ModelSerializer):
    username = serializers.CharField(
        source="user.username",
        read_only=True,
    )
    reactions_count = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()

    class Meta:
        model = JournalEntry
        fields = [
            "id",
            "user",
            "username",
            "date",
            "title",
            "what_i_learned",
            "challenges_faced",
            "key_takeaways",
            "tomorrow_goals",
            "tags",
            "mood",
            "productivity_score",
            "hours_spent",
            "visibility",
            "linked_lessons",
            "linked_flashcard_decks",
            "xp_earned",
            "word_count",
            "version",
            "client_id",
            "is_bookmarked",
            "reactions_count",
            "comments_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "word_count",
            "xp_earned",
            "created_at",
            "updated_at",
        ]

    def get_reactions_count(self, obj):
        return obj.reactions.count()

    def get_comments_count(self, obj):
        return obj.comments.count()


class JournalCommentSerializer(serializers.ModelSerializer):
    username = serializers.CharField(
        source="user.username",
        read_only=True,
    )

    class Meta:
        model = JournalComment
        fields = [
            "id",
            "entry",
            "user",
            "username",
            "content",
            "is_mentor_note",
            "created_at",
        ]
        read_only_fields = ["id", "user", "entry", "created_at"]


class JournalReactionSerializer(serializers.ModelSerializer):
    username = serializers.CharField(
        source="user.username",
        read_only=True,
    )

    class Meta:
        model = JournalReaction
        fields = [
            "id",
            "entry",
            "user",
            "username",
            "reaction_type",
            "created_at",
        ]
        read_only_fields = ["id", "user", "created_at"]


class ReflectionPromptSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReflectionPrompt
        fields = [
            "id",
            "text",
            "prompt_type",
            "category",
            "times_used",
        ]


class UserReflectionStreakSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserReflectionStreak
        fields = [
            "current_streak",
            "longest_streak",
            "last_entry_date",
            "total_entries",
            "total_words_written",
            "total_hours_reflected",
            "average_mood",
            "average_productivity",
            "favorite_day",
            "favorite_tag",
        ]


class WeeklyReflectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeeklyReflection
        fields = [
            "id",
            "week_start",
            "summary",
            "entries_count",
            "total_words",
            "total_hours",
            "average_mood",
            "average_productivity",
            "mood_trend",
            "top_tags",
            "highlights",
            "goals_for_next_week",
            "is_read",
            "created_at",
        ]


class JournalTemplateSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(
        source="created_by.username",
        read_only=True,
    )

    class Meta:
        model = JournalTemplate
        fields = [
            "id",
            "name",
            "description",
            "sections",
            "default_tags",
            "is_public",
            "clone_count",
            "created_by",
            "created_by_username",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "created_by",
            "clone_count",
            "created_at",
        ]


class JournalStatsSerializer(serializers.Serializer):
    total_entries = serializers.IntegerField()
    total_words = serializers.IntegerField()
    total_hours = serializers.FloatField()
    average_mood = serializers.FloatField()
    average_productivity = serializers.FloatField()
    favorite_tag = serializers.CharField(allow_null=True)
    entries_this_week = serializers.IntegerField()
    entries_this_month = serializers.IntegerField()
    mood_distribution = serializers.DictField()
    productivity_trend = serializers.ListField()
    busiest_day = serializers.CharField(allow_null=True)


class WeeklySummaryResponseSerializer(serializers.Serializer):
    week_start = serializers.CharField()
    summary = serializers.CharField()
    entries_count = serializers.IntegerField()
    total_words = serializers.IntegerField()
    total_hours = serializers.FloatField()
    average_mood = serializers.FloatField()
    mood_trend = serializers.CharField()
    top_tags = serializers.ListField()
    highlights = serializers.ListField()


class SocialFeedSerializer(serializers.Serializer):
    entries = serializers.ListField()
    count = serializers.IntegerField()


class StreakResponseSerializer(serializers.Serializer):
    current_streak = serializers.IntegerField()
    longest_streak = serializers.IntegerField()
    total_entries = serializers.IntegerField()


class PromptResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True)
    text = serializers.CharField()
    type = serializers.CharField()
    category = serializers.CharField()
