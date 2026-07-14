from rest_framework import serializers
from apps.moderation.models import ContentReport, ModerationAuditEvent
from django.contrib.contenttypes.models import ContentType


class ContentReportSerializer(serializers.ModelSerializer):
    reporter_username = serializers.CharField(
        source="reporter.username", read_only=True
    )
    content_type_str = serializers.SerializerMethodField()
    content_summary = serializers.SerializerMethodField()

    content_type_app = serializers.CharField(write_only=True)
    content_type_model = serializers.CharField(write_only=True)

    class Meta:
        model = ContentReport
        fields = [
            "id",
            "reporter",
            "reporter_username",
            "content_type",
            "object_id",
            "content_type_str",
            "content_summary",
            "content_type_app",
            "content_type_model",
            "category",
            "description",
            "status",
            "action_taken",
            "created_at",
        ]
        read_only_fields = [
            "reporter",
            "status",
            "action_taken",
            "created_at",
            "content_type",
        ]

    def create(self, validated_data):
        app = validated_data.pop("content_type_app")
        model = validated_data.pop("content_type_model")
        try:
            ct = ContentType.objects.get(app_label=app, model=model)
        except ContentType.DoesNotExist:
            raise serializers.ValidationError(
                {"content_type": "Invalid app or model"}
            )
        validated_data["content_type"] = ct
        return super().create(validated_data)

    def get_content_type_str(self, obj):
        return f"{obj.content_type.app_label}.{obj.content_type.model}"

    def get_content_summary(self, obj):
        if obj.content_object:
            return str(obj.content_object)
        return "Unknown Content"


class ModerationActionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=ContentReport.Status.choices)
    reason = serializers.CharField(required=False, allow_blank=True)


class ModerationAuditEventSerializer(serializers.ModelSerializer):
    moderator_username = serializers.CharField(
        source="moderator.username", read_only=True
    )
    content_report_id = serializers.IntegerField(
        source="content_report.id", read_only=True
    )

    class Meta:
        model = ModerationAuditEvent
        fields = [
            "id",
            "event_type",
            "status_before",
            "status_after",
            "action_taken",
            "reason",
            "created_at",
            "moderator_username",
            "content_report_id",
        ]
        read_only_fields = fields

