from django.contrib.auth import get_user_model
from django.db.models import Count, Max, Q
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics, pagination, permissions, status
from rest_framework.response import Response
from apps.core.throttling import SlidingWindowScopedThrottle
from rest_framework.views import APIView

from .models import DirectMessage, Message, UserPublicKey
from .serializers import (
    ChatRoomSerializer,
    DirectMessageCreateSerializer,
    DirectMessageSerializer,
    MessageCreateSerializer,
    MessageSerializer,
    UserPublicKeySerializer,
)

User = get_user_model()


class MessagePagination(pagination.PageNumberPagination):
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
    throttle_classes = [SlidingWindowScopedThrottle]
    throttle_scope = "chat_message"

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

        room_list = list(rooms)
        from django.contrib.auth import get_user_model

        User = get_user_model()

        for r in room_list:
            if r["room_id"].startswith("dm_"):
                parts = r["room_id"].split("_")
                if len(parts) == 3:
                    try:
                        u1, u2 = int(parts[1]), int(parts[2])
                        other_id = u2 if u1 == request.user.id else u1
                        other_user = User.objects.filter(id=other_id).first()
                        if other_user:
                            r["dm_user"] = other_user.username
                    except ValueError:
                        pass

        serializer = ChatRoomSerializer(room_list, many=True)
        return Response(serializer.data)


class UserPublicKeyView(APIView):
    """
    GET  /api/chat/public-keys/<username>/  — retrieve a user's public key
    POST /api/chat/public-keys/             — publish the authenticated user's public key
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, username):
        try:
            key = UserPublicKey.objects.select_related("user").get(
                user__username=username
            )
        except UserPublicKey.DoesNotExist:
            return Response(
                {"detail": "Public key not found for this user."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(UserPublicKeySerializer(key).data)

    def post(self, request):
        serializer = UserPublicKeySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj, _ = UserPublicKey.objects.update_or_create(
            user=request.user,
            defaults={"public_key": serializer.validated_data["public_key"]},
        )
        return Response(UserPublicKeySerializer(obj).data, status=status.HTTP_200_OK)


class DirectMessageListView(generics.ListAPIView):
    """
    Lists all DMs in the conversation between the authenticated user
    and the specified peer (by username).
    """

    serializer_class = DirectMessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        peer_username = self.kwargs["username"]
        me = self.request.user
        return DirectMessage.objects.filter(
            Q(sender=me, recipient__username=peer_username)
            | Q(sender__username=peer_username, recipient=me)
        ).order_by("created_at")


class DirectMessageCreateView(APIView):
    """
    Send an E2E encrypted direct message to another user.
    The client must encrypt the content before calling this endpoint.
    The server never sees plaintext.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = DirectMessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        try:
            recipient = User.objects.get(username=data["recipient_username"])
        except User.DoesNotExist:
            return Response(
                {"detail": "Recipient not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if recipient == request.user:
            return Response(
                {"detail": "Cannot send a DM to yourself."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        dm = DirectMessage.objects.create(
            sender=request.user,
            recipient=recipient,
            encrypted_content=data["encrypted_content"],
            nonce=data["nonce"],
        )
        return Response(
            DirectMessageSerializer(dm).data, status=status.HTTP_201_CREATED
        )
