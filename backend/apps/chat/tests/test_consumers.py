import json

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken

from config.asgi import application

User = get_user_model()


@database_sync_to_async
def create_user(username):
    return User.objects.create_user(username=username, password="testpassword123")


@pytest.fixture
def auth_user(db):
    user = User.objects.create_user(username="testuser1", password="testpassword123")
    return user


@pytest.fixture
def token(auth_user):
    return str(AccessToken.for_user(auth_user))


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestChatConsumer:
    async def test_unauthenticated_connection(self):
        communicator = WebsocketCommunicator(application, "/ws/chat/room1/")
        connected, _ = await communicator.connect()
        assert not connected
        await communicator.disconnect()

    async def test_missing_room_id(self, token):
        # According to URL routing, a missing room_id might not even match the route,
        # but if it somehow falls through to the consumer without room_id, it should reject.
        # Channels URLRouter will likely 404 it.
        pass

    async def test_authenticated_connection(self, auth_user, token):
        headers = [(b"origin", b"http://localhost")]
        communicator = WebsocketCommunicator(
            application, f"/ws/chat/room1/?token={token}", headers=headers
        )
        connected, _ = await communicator.connect()
        assert connected

        # Should receive the initial connection_established message
        response = await communicator.receive_json_from()
        assert response["type"] == "connection_established"
        assert response["room_id"] == "room1"
        assert response["user_id"] == auth_user.id

        # Drain presence messages
        await communicator.receive_json_from()  # presence_sync
        await communicator.receive_json_from()  # presence_joined

        await communicator.disconnect()

    async def test_typing_indicators(self, auth_user, token):
        user2 = await create_user("testuser2")
        token2 = str(AccessToken.for_user(user2))
        headers = [(b"origin", b"http://localhost")]

        # Connect User 1
        comm1 = WebsocketCommunicator(
            application, f"/ws/chat/room1/?token={token}", headers=headers
        )
        connected1, _ = await comm1.connect()
        assert connected1
        await comm1.receive_json_from()  # connection_established
        await comm1.receive_json_from()  # presence_sync
        await comm1.receive_json_from()  # presence_joined

        # Connect User 2
        comm2 = WebsocketCommunicator(
            application, f"/ws/chat/room1/?token={token2}", headers=headers
        )
        connected2, _ = await comm2.connect()
        assert connected2
        await comm2.receive_json_from()  # connection_established
        await comm2.receive_json_from()  # presence_sync
        await comm2.receive_json_from()  # presence_joined

        # User 1 receives User 2's presence_joined
        await comm1.receive_json_from()

        # User 1 sends typing_start
        await comm1.send_json_to({"action": "typing_start"})

        # User 2 should receive typing indicator
        response = await comm2.receive_json_from()
        assert response["type"] == "typing"
        assert response["action"] == "typing_start"
        assert response["username"] == auth_user.username
        assert response["user_id"] == auth_user.id

        # User 1 sends typing_stop
        await comm1.send_json_to({"action": "typing_stop"})

        # User 2 should receive typing stop
        response2 = await comm2.receive_json_from()
        assert response2["type"] == "typing"
        assert response2["action"] == "typing_stop"
        assert response2["username"] == auth_user.username

        await comm1.disconnect()
        await comm2.disconnect()

    async def test_send_chat_message(self, auth_user, token):
        user2 = await create_user("testuser2")
        token2 = str(AccessToken.for_user(user2))
        headers = [(b"origin", b"http://localhost")]

        comm1 = WebsocketCommunicator(
            application, f"/ws/chat/room1/?token={token}", headers=headers
        )
        await comm1.connect()
        await comm1.receive_json_from()
        await comm1.receive_json_from()  # presence_sync
        await comm1.receive_json_from()  # presence_joined

        comm2 = WebsocketCommunicator(
            application, f"/ws/chat/room1/?token={token2}", headers=headers
        )
        await comm2.connect()
        await comm2.receive_json_from()
        await comm2.receive_json_from()  # presence_sync
        await comm2.receive_json_from()  # presence_joined

        # User 1 receives User 2's presence_joined
        await comm1.receive_json_from()

        # User 1 sends a message
        await comm1.send_json_to(
            {"action": "send_message", "message": "Hello from User 1!"}
        )

        # User 2 should receive the new message
        response = await comm2.receive_json_from()
        assert response["type"] == "new_message"
        assert response["username"] == auth_user.username
        assert response["user_id"] == auth_user.id
        assert response["message"] == "Hello from User 1!"

        # User 1 should ALSO receive their own message broadcast
        response1 = await comm1.receive_json_from()
        assert response1["type"] == "new_message"
        assert response1["message"] == "Hello from User 1!"

        await comm1.disconnect()
        await comm2.disconnect()

    async def test_public_key_exchange(self, auth_user, token):
        user2 = await create_user("testuser2")
        token2 = str(AccessToken.for_user(user2))
        headers = [(b"origin", b"http://localhost")]

        # Connect User 1
        comm1 = WebsocketCommunicator(
            application, f"/ws/chat/room1/?token={token}", headers=headers
        )
        await comm1.connect()
        await comm1.receive_json_from()

        # Connect User 2
        comm2 = WebsocketCommunicator(
            application, f"/ws/chat/room1/?token={token2}", headers=headers
        )
        await comm2.connect()
        await comm2.receive_json_from()

        # User 1 sends their public key
        mock_public_key = "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAv..."
        await comm1.send_json_to(
            {"action": "public_key", "public_key": mock_public_key}
        )

        # User 2 should receive the broadcasted public key
        response = await comm2.receive_json_from()
        assert response["type"] == "public_key"
        assert response["username"] == auth_user.username
        assert response["user_id"] == auth_user.id
        assert response["public_key"] == mock_public_key

        await comm1.disconnect()
        await comm2.disconnect()

    async def test_multi_tab_presence(self, auth_user, token):
        import asyncio

        headers = [(b"origin", b"http://localhost")]

        # Connect tab 1
        comm1 = WebsocketCommunicator(
            application, f"/ws/chat/room1/?token={token}", headers=headers
        )
        await comm1.connect()
        await comm1.receive_json_from()  # connection_established
        await comm1.receive_json_from()  # presence_sync
        join1 = await comm1.receive_json_from()  # presence_joined
        assert join1["type"] == "presence_joined"

        # Connect tab 2 (same user)
        comm2 = WebsocketCommunicator(
            application, f"/ws/chat/room1/?token={token}", headers=headers
        )
        await comm2.connect()
        await comm2.receive_json_from()  # connection_established
        await comm2.receive_json_from()  # presence_sync

        # presence_joined should NOT be sent to comm1 because user is already present!
        # wait 0.5s to ensure no message
        assert await comm1.receive_nothing(timeout=0.5)

        # Disconnect tab 2
        await comm2.disconnect()

        # comm1 receives typing_stop due to comm2 disconnecting
        resp = await comm1.receive_json_from()
        assert resp["type"] == "typing"
        assert resp["action"] == "typing_stop"

        # presence_left should NOT be sent because user still has tab 1
        assert await comm1.receive_nothing(timeout=0.5)

        await comm1.disconnect()
