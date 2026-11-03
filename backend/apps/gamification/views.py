from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework import (
    generics,
    pagination,
    permissions,
    serializers,
    status,
    views,
    viewsets,
)
from rest_framework.response import Response

from .models import Badge, Purchase, Quest, ShopItem, Streak, UserAchievement, UserQuest


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


class QuestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quest
        fields = "__all__"


class UserQuestSerializer(serializers.ModelSerializer):
    quest = QuestSerializer(read_only=True)

    class Meta:
        model = UserQuest
        fields = [
            "id",
            "quest",
            "progress",
            "completed",
            "reward_claimed",
            "assigned_at",
            "expires_at",
        ]


class BadgeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Badge.objects.all()
    serializer_class = BadgeSerializer
    permission_classes = [permissions.AllowAny]


class MyAchievementsPagination(pagination.PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class MyAchievementsView(generics.ListAPIView):
    serializer_class = UserAchievementSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = MyAchievementsPagination

    def get_queryset(self):
        return UserAchievement.objects.filter(user=self.request.user).order_by(
            "-awarded_at", "-id"
        )


class MyStreakView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        streak, _ = Streak.objects.get_or_create(user=request.user)
        serializer = StreakSerializer(streak)
        return Response(serializer.data)


class MyQuestsView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        quests = UserQuest.objects.filter(
            user=request.user,
            expires_at__gte=timezone.now(),
        ).select_related("quest")
        serializer = UserQuestSerializer(quests, many=True)
        return Response(serializer.data)

    def post(self, request):
        from apps.progress.models import XPEvent

        quest_id = request.data.get("quest_id")
        with transaction.atomic():  # type: ignore
            # Flip the flag first with a conditional UPDATE: the DB only lets one
            # concurrent request match reward_claimed=False, the rest get 0 rows.
            claimed = UserQuest._default_manager.filter(
                id=quest_id,
                user=request.user,
                completed=True,
                reward_claimed=False,
                expires_at__gte=timezone.now(),
            ).update(reward_claimed=True)
            if not claimed:
                return Response(
                    {"error": "Quest not found or already claimed"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            user_quest = UserQuest._default_manager.select_related("quest").get(
                id=quest_id
            )
            reward = user_quest.quest.xp_reward
            XPEvent._default_manager.create(
                user=request.user,
                source_type="milestone",
                source_id=user_quest.quest_id,
                # base_points is capped at 1000 by a DB constraint
                base_points=min(reward, 1000),
                multiplier=1.0,
                xp_delta=reward,
            )

        return Response({"xp_awarded": user_quest.quest.xp_reward})


class ShopItemSerializer(serializers.ModelSerializer):
    already_purchased = serializers.SerializerMethodField()

    class Meta:
        model = ShopItem
        fields = [
            "id",
            "name",
            "description",
            "item_type",
            "cost",
            "icon_emoji",
            "is_limited",
            "is_active",
            "already_purchased",
        ]

    def get_already_purchased(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return Purchase.objects.filter(user=request.user, item=obj).exists()
        return False


class ShopItemListView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        items = ShopItem.objects.filter(is_active=True)
        serializer = ShopItemSerializer(items, many=True, context={"request": request})
        return Response(serializer.data)


class PurchaseSerializer(serializers.ModelSerializer):
    item = ShopItemSerializer(read_only=True)

    class Meta:
        model = Purchase
        fields = ["id", "item", "xp_spent", "purchased_at"]


class PurchaseHistoryView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        purchases = Purchase.objects.filter(user=request.user).select_related("item")
        serializer = PurchaseSerializer(purchases, many=True)
        return Response(serializer.data)


class PurchaseItemView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from django.db import transaction

        from apps.progress.models import XPEvent

        item_id = request.data.get("item_id")
        try:
            item = ShopItem.objects.get(id=item_id, is_active=True)
        except ShopItem.DoesNotExist:
            return Response(
                {"error": "Item not found"}, status=status.HTTP_404_NOT_FOUND
            )

        with transaction.atomic():
            # Lock the user's XP rows to prevent concurrent balance reads
            user_xp_events = XPEvent.objects.select_for_update().filter(
                user=request.user
            )
            total_xp = user_xp_events.aggregate(total=Sum("xp_delta"))["total"] or 0

            if item.is_limited:
                existing = Purchase.objects.filter(
                    user=request.user, item=item
                ).exists()
                if existing:
                    return Response(
                        {"error": "You already own this item"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            if total_xp < item.cost:
                return Response(
                    {
                        "error": f"Not enough XP. You need {item.cost} XP but have {total_xp}"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            XPEvent.objects.create(
                user=request.user,
                source_type="shop",
                source_id=item.id,
                base_points=item.cost,
                multiplier=1.0,
                xp_delta=-item.cost,
            )

            Purchase.objects.create(user=request.user, item=item, xp_spent=item.cost)

            if item.item_type == "streak_freeze":
                from apps.progress.models import StreakProfile

                streak_profile, _ = StreakProfile.objects.get_or_create(
                    user=request.user
                )
                streak_profile.streak_freezes += 1
                streak_profile.save(update_fields=["streak_freezes"])

        return Response(
            {
                "success": True,
                "item": item.name,
                "xp_spent": item.cost,
                "remaining_xp": total_xp - item.cost,
            }
        )


class MyXpView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from apps.progress.models import XPEvent

        total = (
            XPEvent.objects.filter(user=request.user).aggregate(total=Sum("xp_delta"))[
                "total"
            ]
            or 0
        )
        return Response({"total_xp": total})
