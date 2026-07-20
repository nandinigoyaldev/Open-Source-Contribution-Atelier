from rest_framework import permissions, serializers, views, viewsets
from rest_framework.response import Response

from .models import Badge, Streak, UserAchievement


class BadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Badge
        fields = "__all__"


class UserAchievementSerializer(serializers.ModelSerializer):
    badge = BadgeSerializer(read_only=True)

    class Meta:
        model = UserAchievement
        fields = "__all__"


class StreakSerializer(serializers.ModelSerializer):
    class Meta:
        model = Streak
        fields = ["current_streak", "longest_streak", "last_activity_date"]


class BadgeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Badge.objects.all()
    serializer_class = BadgeSerializer
    permission_classes = [permissions.AllowAny]


class MyAchievementsView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        achievements = UserAchievement.objects.filter(user=request.user)
        serializer = UserAchievementSerializer(achievements, many=True)
        return Response(serializer.data)


class MyStreakView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        streak, _ = Streak.objects.get_or_create(user=request.user)
        serializer = StreakSerializer(streak)
        return Response(serializer.data)
