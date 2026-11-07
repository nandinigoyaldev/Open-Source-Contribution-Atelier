from rest_framework import serializers

from .models import (
    Badge,
    Certificate,
    HelpRequest,
    LessonProgress,
    QuizAttempt,
    UserBadge,
    WeeklyGoal,
)

EXPECTED_VERSION_HELP = (
    "Version of this lesson's progress the client last saw, 0 if it saw none. "
    "A mismatch is refused as a conflict. Without it the write can only move "
    "progress forward."
)


class BadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Badge
        fields = "__all__"


class DailyProgressSerializer(serializers.Serializer):
    date = serializers.DateField()
    count = serializers.IntegerField()
    lessons = serializers.ListField(child=serializers.CharField(), required=False)


class UserBadgeSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField(source="badge.id")
    name = serializers.ReadOnlyField(source="badge.name")
    slug = serializers.ReadOnlyField(source="badge.slug")
    description = serializers.ReadOnlyField(source="badge.description")
    icon_url = serializers.SerializerMethodField()

    class Meta:
        model = UserBadge
        fields = ["id", "name", "slug", "description", "earned_at", "icon_url"]

    def get_icon_url(self, user_badge):
        val = getattr(user_badge.badge, "icon_asset_url", None)
        return val if val else None


class LessonProgressSerializer(serializers.ModelSerializer):
    lesson_slug = serializers.ReadOnlyField(source="lesson.slug")

    class Meta:
        model = LessonProgress
        fields = [
            "id",
            "user",
            "lesson",
            "lesson_slug",
            "completed",
            "score",
            "attempt_count",
            "version",
            "updated_at",
        ]


class HelpRequestSerializer(serializers.ModelSerializer):
    lesson_slug = serializers.ReadOnlyField(source="lesson.slug")

    class Meta:
        model = HelpRequest
        fields = [
            "id",
            "user",
            "lesson",
            "lesson_slug",
            "message",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["user", "status", "created_at", "updated_at"]


class LessonProgressCreateSerializer(serializers.Serializer):
    lesson_slug = serializers.SlugField(help_text="Slug of the lesson")
    score = serializers.IntegerField(default=100, help_text="Numeric score")
    completed = serializers.BooleanField(
        default=True, help_text="Whether the lesson is completed"
    )
    client_timestamp = serializers.IntegerField(
        required=False, help_text="Client timestamp, stored with the sync record"
    )
    expected_version = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=0,
        help_text=EXPECTED_VERSION_HELP,
    )
    idempotency_key = serializers.CharField(
        max_length=255,
        required=False,
        help_text="Client-generated idempotency key per completion attempt",
    )


class BulkLessonProgressSerializer(serializers.Serializer):
    lesson_slug = serializers.SlugField()
    score = serializers.IntegerField(default=100)
    completed = serializers.BooleanField(default=True)
    client_timestamp = serializers.IntegerField(required=False)
    expected_version = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=0,
        help_text=EXPECTED_VERSION_HELP,
    )
    idempotency_key = serializers.CharField(
        max_length=255,
        required=False,
        help_text="Client-generated idempotency key per completion attempt",
    )


class BulkSyncSerializer(serializers.Serializer):
    lessons = BulkLessonProgressSerializer(many=True)


class CertificateVerificationSerializer(serializers.ModelSerializer):
    learner_name = serializers.SerializerMethodField()

    class Meta:
        model = Certificate
        fields = [
            "verification_hash",
            "course_name",
            "issued_at",
            "learner_name",
            "is_active",
        ]

    def get_learner_name(self, obj):
        return obj.user.get_full_name() or obj.user.username


class QuizAttemptSerializer(serializers.ModelSerializer):
    client_timestamp = serializers.IntegerField(required=False, write_only=True)

    class Meta:
        model = QuizAttempt
        fields = [
            "id",
            "user",
            "question_id",
            "question_text",
            "selected_answer",
            "correct_answer",
            "is_correct",
            "time_taken_seconds",
            "client_timestamp",
            "created_at",
        ]
        read_only_fields = ["id", "user", "created_at"]


from .models import CodeSubmission, PeerReview


class CodeSubmissionSerializer(serializers.ModelSerializer):
    username = serializers.ReadOnlyField(source="user.username")
    client_timestamp = serializers.IntegerField(required=False, write_only=True)

    class Meta:
        model = CodeSubmission
        fields = [
            "id",
            "user",
            "username",
            "exercise",
            "title",
            "code_snippet",
            "description",
            "status",
            "client_timestamp",
            "created_at",
        ]
        read_only_fields = ["id", "user", "username", "status", "created_at"]


class PeerReviewSerializer(serializers.ModelSerializer):
    reviewer_username = serializers.ReadOnlyField(source="reviewer.username")

    class Meta:
        model = PeerReview
        fields = [
            "id",
            "submission",
            "reviewer",
            "reviewer_username",
            "feedback",
            "rating",
            "is_approved",
            "points_earned",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "submission",
            "reviewer",
            "reviewer_username",
            "points_earned",
            "created_at",
        ]


class WeeklyGoalSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeeklyGoal
        fields = [
            "id",
            "week_start_date",
            "target_lessons",
            "target_xp",
            "target_minutes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "week_start_date", "created_at", "updated_at"]

    def validate_target_lessons(self, value):
        if value < 1 or value > 100:
            raise serializers.ValidationError(
                "Target lessons must be between 1 and 100."
            )
        return value

    def validate_target_xp(self, value):
        if value < 10 or value > 50000:
            raise serializers.ValidationError(
                "Target XP must be between 10 and 50,000."
            )
        return value

    def validate_target_minutes(self, value):
        if value < 10 or value > 10080:
            raise serializers.ValidationError(
                "Target minutes must be between 10 and 10,080."
            )
        return value
