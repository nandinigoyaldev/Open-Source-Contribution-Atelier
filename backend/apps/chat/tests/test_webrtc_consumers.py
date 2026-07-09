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
class TestWebRTCSignalingConsumer:
    async def test_unauthenticated_connection(self):
        communicator = WebsocketCommunicator(application, "/ws/webrtc/room1/")
        connected, _ = await communicator.connect()
        assert not connected
        await communicator.disconnect()

    async def test_authenticated_connection(self, auth_user, token):
        headers = [(b"origin", b"http://localhost")]
        communicator = WebsocketCommunicator(
            application, f"/ws/webrtc/room1/?token={token}", headers=headers
        )
        connected, _ = await communicator.connect()
        assert connected

        await communicator.disconnect()

    async def test_peer_joined_and_left(self, auth_user, token):
        user2 = await create_user("testuser2")
        token2 = str(AccessToken.for_user(user2))
        headers = [(b"origin", b"http://localhost")]

        # Connect User 1
        comm1 = WebsocketCommunicator(
            application, f"/ws/webrtc/room1/?token={token}", headers=headers
        )
        connected1, _ = await comm1.connect()
        assert connected1

        # Connect User 2
        comm2 = WebsocketCommunicator(
            application, f"/ws/webrtc/room1/?token={token2}", headers=headers
        )
        connected2, _ = await comm2.connect()
        assert connected2

        # User 1 should receive peer_joined when User 2 connects
        response = await comm1.receive_json_from()
        assert response["type"] == "peer_joined"
        assert response["username"] == "testuser2"
        assert response["user_id"] == user2.id

        # User 2 disconnects
        await comm2.disconnect()

        # User 1 should receive peer_left
        response2 = await comm1.receive_json_from()
        assert response2["type"] == "peer_left"
        assert response2["username"] == "testuser2"
        assert response2["user_id"] == user2.id

        await comm1.disconnect()

    async def test_webrtc_signaling(self, auth_user, token):
        user2 = await create_user("testuser3")
        token2 = str(AccessToken.for_user(user2))
        headers = [(b"origin", b"http://localhost")]

        comm1 = WebsocketCommunicator(
            application, f"/ws/webrtc/room1/?token={token}", headers=headers
        )
        await comm1.connect()

        comm2 = WebsocketCommunicator(
            application, f"/ws/webrtc/room1/?token={token2}", headers=headers
        )
        await comm2.connect()
        await comm1.receive_json_from()  # Consume peer_joined message

        # User 1 sends an offer
        await comm1.send_json_to({"action": "offer", "data": {"sdp": "dummy_offer_sdp"}})

        # User 2 should receive the offer
        response = await comm2.receive_json_from()
        assert response["type"] == "webrtc_signal"
        assert response["action"] == "offer"
        assert response["data"] == {"sdp": "dummy_offer_sdp"}

        # User 2 sends an answer
        await comm2.send_json_to({"action": "answer", "data": {"sdp": "dummy_answer_sdp"}})
        
        # User 1 receives the answer
        response2 = await comm1.receive_json_from()
        assert response2["type"] == "webrtc_signal"
        assert response2["action"] == "answer"
        assert response2["data"] == {"sdp": "dummy_answer_sdp"}

        await comm1.disconnect()
        await comm2.disconnect()
