from rest_framework import serializers

from apps.issues.models import IssueReport


class IssueReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = IssueReport
        fields = [
            "id",
            "title",
            "description",
            "issue_type",
            "status",
            "url_path",
            "user",
            "image",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "user", "created_at", "updated_at"]

    def create(self, validated_data):
        request = self.context.get("request")
        if request and hasattr(request, "user") and request.user.is_authenticated:
            validated_data["user"] = request.user
        return super().create(validated_data)


from apps.issues.models import Bounty, BountySubmission


class BountySerializer(serializers.ModelSerializer):
    claimed_by_username = serializers.CharField(
        source="claimed_by.username", read_only=True
    )

    class Meta:
        model = Bounty
        fields = [
            "id",
            "title",
            "description",
            "xp_reward",
            "status",
            "claimed_by",
            "claimed_by_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class BountySubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = BountySubmission
        fields = [
            "id",
            "bounty",
            "user",
            "code_patch",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "user", "status", "created_at", "updated_at"]
