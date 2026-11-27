# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportOperatorIssue=false, reportReturnType=false, reportGeneralTypeIssues=false
# (Django model/field types are unresolved without stubs; these rules are noise here.)
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.progress.services import adaptive_difficulty as adaptive


class AdaptiveDifficultySettingsSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    skill_rating = serializers.FloatField(read_only=True)
    rating_deviation = serializers.FloatField(read_only=True)
    level = serializers.ChoiceField(
        choices=[adaptive.GUIDED, adaptive.STANDARD, adaptive.EXPERT], read_only=True
    )


def _payload(profile) -> dict:
    return {
        "enabled": profile.adaptive_difficulty_enabled,
        "skill_rating": round(profile.skill_rating, 1),
        "rating_deviation": round(profile.rating_deviation, 1),
        "level": adaptive.scaffolding_level(profile.skill_rating),
    }


class AdaptiveDifficultySettingsView(APIView):
    """The learner's opt-in switch and current rating."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses=AdaptiveDifficultySettingsSerializer)
    def get(self, request):
        return Response(_payload(adaptive.profile_for(request.user)))

    @extend_schema(
        request=AdaptiveDifficultySettingsSerializer,
        responses=AdaptiveDifficultySettingsSerializer,
    )
    def put(self, request):
        serializer = AdaptiveDifficultySettingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict = serializer.validated_data  # pyright: ignore[reportAssignmentType]
        profile = adaptive.set_enabled(request.user, data["enabled"])
        return Response(_payload(profile))
