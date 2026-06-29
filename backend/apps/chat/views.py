from django.db.models import Count, Max
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics, permissions, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Message
from .serializers import (
    ChatRoomSerializer,
    MessageCreateSerializer,
    MessageSerializer,
)


class MessagePagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


@extend_schema_view(
    get=extend_schema(
        summary="List chat messages for a room",
        description=(
            "Returns a paginated list of messages for the given `room_id`. "
            "Results are ordered chronologically (oldest first). "
            "Use the `page` and `page_size` query parameters to paginate."
        ),
        responses={
            200: MessageSerializer(many=True),
            401: OpenApiResponse(
                description="Authentication credentials were not provided."
            ),
        },
        tags=["chat"],
    ),
)
class MessageListView(generics.ListAPIView):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = MessagePagination

    def get_queryset(self):
        room_id = self.kwargs["room_id"]
        return Message.objects.filter(room_id=room_id).select_related("user")


@extend_schema_view(
    post=extend_schema(
        summary="Send a chat message",
        description=(
            "Creates a new message in the specified `room_id`. "
            "The message is broadcast to all connected WebSocket clients in the same room."
        ),
        request=MessageCreateSerializer,
        responses={
            201: MessageSerializer,
            400: OpenApiResponse(description="Validation error (e.g. empty content)."),
            401: OpenApiResponse(
                description="Authentication credentials were not provided."
            ),
        },
        tags=["chat"],
    ),
)
class MessageCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, room_id):
        serializer = MessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message = Message.objects.create(
            user=request.user,
            room_id=room_id,
            content=serializer.validated_data["content"],  # type: ignore
        )

        response_serializer = MessageSerializer(message)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(
        summary="List chat rooms with recent activity",
        description=(
            "Returns a list of chat rooms the current user has participated in, "
            "along with the last message, timestamp, and participant count. "
            "Results are ordered by most recent activity first."
        ),
        responses={
            200: ChatRoomSerializer(many=True),
            401: OpenApiResponse(
                description="Authentication credentials were not provided."
            ),
        },
        tags=["chat"],
    ),
)
class ChatRoomListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user_rooms = (
            Message.objects.filter(user=request.user)
            .values_list("room_id", flat=True)
            .distinct()
        )

        rooms = (
            Message.objects.filter(room_id__in=user_rooms)
            .values("room_id")
            .annotate(
                last_message=Max("content"),
                last_message_at=Max("created_at"),
                participant_count=Count("user", distinct=True),
            )
            .order_by("-last_message_at")
        )

        serializer = ChatRoomSerializer(rooms, many=True)
        return Response(serializer.data)
