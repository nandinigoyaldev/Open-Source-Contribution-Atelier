from rest_framework import serializers

from .models import Badge, HelpRequest, LessonProgress, UserBadge


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
        return getattr(user_badge.badge, "icon_url", None)


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
