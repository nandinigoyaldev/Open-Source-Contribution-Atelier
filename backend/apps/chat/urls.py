from django.urls import path

from .views import ChatRoomListView, MessageCreateView, MessageListView

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
]
