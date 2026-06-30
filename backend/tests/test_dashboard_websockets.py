import pytest
from apps.content.models import Lesson
from apps.progress.models import LessonProgress
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from config.asgi import application
from django.contrib.auth.models import User


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_leaderboard_websocket_update():
    # Create test data
    user = await User.objects.acreate(username="test_user", password="password")
    lesson = await Lesson.objects.acreate(
        title="Test Lesson", slug="test-lesson", estimated_minutes=10, order=1
    )

    # Generate a real JWT access token so JWTAuthMiddleware can authenticate the user
    from rest_framework_simplejwt.tokens import AccessToken

    token = str(AccessToken.for_user(user))

    # Connect with the token in the query string (how JWTAuthMiddleware reads it)
    communicator = WebsocketCommunicator(
        application,
        f"/ws/leaderboard/?token={token}",
        headers=[(b"origin", b"http://localhost")],
    )
    connected, subprotocol = await communicator.connect()
    assert connected

    # Trigger lesson completion
    await LessonProgress.objects.acreate(
        user=user, lesson=lesson, completed=True, score=50
    )

    # Wait for message
    response = await communicator.receive_json_from(timeout=2)
    assert response["type"] == "leaderboard_update"
    assert response["event"] == "xp_update"
    assert response["user_id"] == user.id
    assert response["username"] == user.username
    assert response["xp"] >= 50

    await communicator.disconnect()
