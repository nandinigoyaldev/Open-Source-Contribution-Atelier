from django.urls import path

from .views import (
    ChatRoomListView,
    DirectMessageCreateView,
    DirectMessageListView,
    MessageCreateView,
    MessageListView,
    UserPublicKeyView,
)

app_name = "chat"

urlpatterns = [
    path("rooms/", ChatRoomListView.as_view(), name="chat-room-list"),
    path(
        "rooms/<str:room_id>/messages/",
        MessageListView.as_view(),
        name="chat-message-list",
    ),
    path(
        "rooms/<str:room_id>/messages/send/",
        MessageCreateView.as_view(),
        name="chat-message-create",
    ),
    # E2E Encrypted Direct Messages
    path("dm/send/", DirectMessageCreateView.as_view(), name="dm-create"),
    path("dm/<str:username>/", DirectMessageListView.as_view(), name="dm-list"),
    # Public key registry
    path("public-keys/", UserPublicKeyView.as_view(), name="public-key-publish"),
    path(
        "public-keys/<str:username>/",
        UserPublicKeyView.as_view(),
        name="public-key-get",
    ),
]
