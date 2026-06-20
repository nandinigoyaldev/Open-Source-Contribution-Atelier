from rest_framework import serializers

from .models import Badge, HelpRequest, LessonProgress, UserBadge, Certificate


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
        fields = ["id", "user", "lesson", "lesson_slug", "completed", "score", "attempt_count", "updated_at"]


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
    completed = serializers.BooleanField(default=True, help_text="Whether the lesson is completed")

class CertificateVerificationSerializer(serializers.ModelSerializer):
    learner_name = serializers.SerializerMethodField()

    class Meta:
        model = Certificate
        fields = ["verification_hash", "course_name", "issued_at", "learner_name", "is_active"]

    def get_learner_name(self, obj):
        return obj.user.get_full_name() or obj.user.username