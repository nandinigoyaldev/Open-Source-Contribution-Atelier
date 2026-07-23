from rest_framework import serializers

from .models import MaintainerWorkloadProfile, RepoHealthScore


class RepoHealthScoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = RepoHealthScore
        fields = [
            "id",
            "repo_url",
            "repo_owner",
            "repo_name",
            "open_issues",
            "closed_issues",
            "open_prs",
            "closed_prs",
            "avg_pr_close_days",
            "contributor_count",
            "last_commit_days_ago",
            "sentiment_score",
            "sentiment_label",
            "health_score",
            "red_flags",
            "green_flags",
            "updated_at",
        ]
        read_only_fields = fields


class MaintainerWorkloadProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaintainerWorkloadProfile
        fields = [
            "active_prs_assigned",
            "avg_time_to_review_hours",
            "recent_issue_volume",
            "burnout_risk_score",
            "last_analyzed_at",
        ]
        read_only_fields = ["burnout_risk_score", "last_analyzed_at"]
