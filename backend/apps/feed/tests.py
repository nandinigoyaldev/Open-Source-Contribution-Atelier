"""
Tests for FeedConsumer authentication and channel isolation.

@file tests.py
@location backend/apps/feed/tests.py
"""

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken

from apps.organizations.models import Organization
from config.asgi import application

User = get_user_model()


@database_sync_to_async
def create_user(username, organization=None):
    user = User.objects.create_user(username=username, password="testpassword123")
    if organization is not None:
        from apps.accounts.models import UserProfile

        UserProfile.objects.update_or_create(
            user=user, defaults={"organization": organization}
        )
    return user


@database_sync_to_async
def create_organization(name):
    return Organization.objects.create(name=name)


@pytest.fixture
def token_for():
    def _token_for(user):
        return str(AccessToken.for_user(user))

    return _token_for


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestFeedConsumer:
    async def test_unauthenticated_connection_rejected(self):
        communicator = WebsocketCommunicator(application, "/ws/feed/")
        connected, subprotocol = await communicator.connect()
        assert not connected
        await communicator.disconnect()

    async def test_invalid_token_rejected(self):
        communicator = WebsocketCommunicator(
            application, "/ws/feed/?token=not-a-real-token"
        )
        connected, _ = await communicator.connect()
        assert not connected
        await communicator.disconnect()

    async def test_authenticated_connection_accepted(self, token_for):
        user = await create_user("feeduser1")
        token = token_for(user)
        communicator = WebsocketCommunicator(application, f"/ws/feed/?token={token}")
        connected, _ = await communicator.connect()
        assert connected
        await communicator.disconnect()

    async def test_ping_pong(self, token_for):
        user = await create_user("feeduser2")
        token = token_for(user)
        communicator = WebsocketCommunicator(application, f"/ws/feed/?token={token}")
        connected, _ = await communicator.connect()
        assert connected

        await communicator.send_json_to({"action": "ping"})
        response = await communicator.receive_json_from()
        assert response == {"type": "pong"}

        await communicator.disconnect()

    async def test_users_only_receive_events_from_their_own_group(self, token_for):
        """
        User isolation: an event sent to user A's personal group must not
        be delivered to user B's connection.
        """
        from channels.layers import get_channel_layer

        user_a = await create_user("feeduser_a")
        user_b = await create_user("feeduser_b")

        comm_a = WebsocketCommunicator(
            application, f"/ws/feed/?token={token_for(user_a)}"
        )
        comm_b = WebsocketCommunicator(
            application, f"/ws/feed/?token={token_for(user_b)}"
        )
        assert (await comm_a.connect())[0]
        assert (await comm_b.connect())[0]

        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"feed_user_{user_a.id}",
            {"type": "feed_event", "data": {"event": "only_for_a"}},
        )

        # A receives it
        message = await comm_a.receive_json_from()
        assert message == {"event": "only_for_a"}

        # B must NOT receive it
        assert await comm_b.receive_nothing(timeout=0.2)

        await comm_a.disconnect()
        await comm_b.disconnect()

    async def test_org_group_scoping(self, token_for):
        """
        Users in the same organization both receive an org-broadcast
        event; a user in a different (or no) organization does not.
        """
        from channels.layers import get_channel_layer

        org = await create_organization("Acme Corp")
        other_org = await create_organization("Other Corp")

        member_1 = await create_user("org_member_1", organization=org)
        member_2 = await create_user("org_member_2", organization=org)
        outsider = await create_user("org_outsider", organization=other_org)

        comm_1 = WebsocketCommunicator(
            application, f"/ws/feed/?token={token_for(member_1)}"
        )
        comm_2 = WebsocketCommunicator(
            application, f"/ws/feed/?token={token_for(member_2)}"
        )
        comm_outsider = WebsocketCommunicator(
            application, f"/ws/feed/?token={token_for(outsider)}"
        )
        assert (await comm_1.connect())[0]
        assert (await comm_2.connect())[0]
        assert (await comm_outsider.connect())[0]

        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"feed_org_{org.id}",
            {"type": "feed_event", "data": {"event": "org_wide"}},
        )

        assert await comm_1.receive_json_from() == {"event": "org_wide"}
        assert await comm_2.receive_json_from() == {"event": "org_wide"}
        assert await comm_outsider.receive_nothing(timeout=0.2)

        await comm_1.disconnect()
        await comm_2.disconnect()
        await comm_outsider.disconnect()
