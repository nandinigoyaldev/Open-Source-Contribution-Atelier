import json

import pytest
from apps.notifications.models import Notification
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from config.asgi import application
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()


@database_sync_to_async
def create_user():
    return User.objects.create_user(username="testuser", password="testpassword123")


@database_sync_to_async
def create_notification(user):
    return Notification.objects.create(
        recipient=user, title="Test", message="Test message", notification_type="system"
    )


@database_sync_to_async
def is_notification_read(notif_id):
    return Notification.objects.get(id=notif_id).is_read


@pytest.fixture
def auth_user(db):
    user = User.objects.create_user(username="testuser", password="testpassword123")
    return user


@pytest.fixture
def token(auth_user):
    return str(AccessToken.for_user(auth_user))


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestNotificationConsumer:
    async def test_unauthenticated_connection(self):
        communicator = WebsocketCommunicator(application, "/ws/notifications/")
        connected, _ = await communicator.connect()
        assert not connected
        await communicator.disconnect()

    async def test_authenticated_connection(self, auth_user, token):
        await create_notification(auth_user)

        communicator = WebsocketCommunicator(
            application, f"/ws/notifications/?token={token}"
        )
        connected, _ = await communicator.connect()
        assert connected

        # Should receive the initial connection_established message with unread_count=1
        response = await communicator.receive_json_from()
        assert response["type"] == "connection_established"
        assert response["unread_count"] == 1

        await communicator.disconnect()

    async def test_mark_read_action(self, auth_user, token):
        notif = await create_notification(auth_user)

        communicator = WebsocketCommunicator(
            application, f"/ws/notifications/?token={token}"
        )
        connected, _ = await communicator.connect()
        assert connected

        # Consume the connection_established message
        await communicator.receive_json_from()

        # Send mark_read action
        await communicator.send_json_to(
            {"action": "mark_read", "notification_id": str(notif.id)}
        )

        # Wait for the marked_read confirmation
        response = await communicator.receive_json_from()
        assert response["type"] == "marked_read"
        assert response["notification_id"] == str(notif.id)

        # Verify DB update
        is_read = await is_notification_read(notif.id)
        assert is_read is True

        await communicator.disconnect()

    async def test_broadcast_notification(self, auth_user, token):
        communicator = WebsocketCommunicator(
            application, f"/ws/notifications/?token={token}"
        )
        connected, _ = await communicator.connect()
        assert connected
        await communicator.receive_json_from()

        channel_layer = get_channel_layer()
        group_name = f"notifications_{auth_user.id}"

        await channel_layer.group_send(
            group_name,
            {
                "type": "send_notification",
                "notification": {"id": "123", "title": "Broadcast Test"},
            },
        )

        response = await communicator.receive_json_from()
        assert response["type"] == "notification"
        assert response["notification"]["title"] == "Broadcast Test"

        await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestLeaderboardConsumer:
    async def test_unauthenticated_connection(self):
        communicator = WebsocketCommunicator(application, "/ws/leaderboard/")
        connected, _ = await communicator.connect()
        assert not connected
        await communicator.disconnect()

    async def test_authenticated_connection(self, token):
        communicator = WebsocketCommunicator(
            application, f"/ws/leaderboard/?token={token}"
        )
        connected, _ = await communicator.connect()
        assert connected
        await communicator.disconnect()

    async def test_broadcast_leaderboard_update(self, token):
        communicator = WebsocketCommunicator(
            application, f"/ws/leaderboard/?token={token}"
        )
        connected, _ = await communicator.connect()
        assert connected

        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            "leaderboard",
            {
                "type": "leaderboard_update",
                "event": "xp_update",
                "user_id": 1,
                "username": "testuser",
                "xp": 100,
                "message": "User leveled up!",
            },
        )

        response = await communicator.receive_json_from()
        assert response["type"] == "leaderboard_update"
        assert response["username"] == "testuser"
        assert response["xp"] == 100

        await communicator.disconnect()
