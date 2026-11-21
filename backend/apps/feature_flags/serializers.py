from rest_framework import serializers

from apps.feature_flags.models import FeatureFlag, FeatureFlagAuditLog
from apps.feature_flags.services import current_environment, normalize_environments


class FeatureFlagAuditLogSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source="actor.username", read_only=True)

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
    change_reason = serializers.CharField(write_only=True, required=False, default="")

    class Meta:
        model = FeatureFlag
        fields = [
            "id",
            "name",
            "description",
            "flag_type",
            "is_active",
            "kill_switch",
            "default_value",
            "rollout_percentage",
            "environments",
            "target_organizations",
            "target_users",
            "requires_approval",
            "approved_by",
            "change_reason",
            "created_at",
            "updated_at",
        ]
        # The kill switch only moves through the audited kill-switch action.
        read_only_fields = ["id", "kill_switch", "created_at", "updated_at"]

    def validate_environments(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Expected a list of environment names.")
        return normalize_environments(value)


class FeatureFlagSummarySerializer(serializers.ModelSerializer):
    """
    What the admin flags page lists: scope and rollout impact only.

    Targeted user and organization identifiers are replaced by counts so the
    list never ships who is in a rollout; the detail endpoint still has them.
    """

    target_users_count = serializers.SerializerMethodField()
    target_organizations_count = serializers.SerializerMethodField()
    applies_in_current_environment = serializers.SerializerMethodField()

    class Meta:
        model = FeatureFlag
        fields = [
            "id",
            "name",
            "description",
            "flag_type",
            "is_active",
            "kill_switch",
            "default_value",
            "rollout_percentage",
            "environments",
            "applies_in_current_environment",
            "target_users_count",
            "target_organizations_count",
            "updated_at",
        ]

    def get_target_users_count(self, obj) -> int:
        return len(obj.target_users or [])

    def get_target_organizations_count(self, obj) -> int:
        return len(obj.target_organizations or [])

    def get_applies_in_current_environment(self, obj) -> bool:
        scoped = normalize_environments(obj.environments)
        return not scoped or current_environment() in scoped
