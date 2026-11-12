from rest_framework import serializers

from apps.feature_flags.models import FeatureFlag, FeatureFlagAuditLog


class FeatureFlagAuditLogSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(
        source="actor.username", read_only=True
    )

    class Meta:
        model = FeatureFlagAuditLog
        fields = [
            "id",
            "flag",
            "actor",
            "actor_username",
            "action",
            "scope",
            "old_values",
            "new_values",
            "reason",
            "timestamp",
        ]


class FeatureFlagSerializer(serializers.ModelSerializer):
    change_reason = serializers.CharField(
        write_only=True, required=False, default=""
    )

    class Meta:
        model = FeatureFlag
        fields = [
            "id",
            "name",
            "description",
            "flag_type",
            "is_active",
            "default_value",
            "rollout_percentage",
            "target_organizations",
            "target_users",
            "requires_approval",
            "approved_by",
            "change_reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
