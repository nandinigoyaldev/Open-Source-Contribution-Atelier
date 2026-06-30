from rest_framework import serializers

from .models import (
    Badge,
    Certificate,
    HelpRequest,
    LessonProgress,
    QuizAttempt,
    UserBadge,
)


class BadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Badge
        fields = "__all__"


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
    client_timestamp = serializers.IntegerField(required=False, help_text="Client timestamp for conflict resolution")


class BulkLessonProgressSerializer(serializers.Serializer):
    lesson_slug = serializers.SlugField()
    score = serializers.IntegerField(default=100)
    completed = serializers.BooleanField(default=True)
    client_timestamp = serializers.IntegerField(required=False)


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
            "title",
            "code_snippet",
            "description",
            "status",
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
