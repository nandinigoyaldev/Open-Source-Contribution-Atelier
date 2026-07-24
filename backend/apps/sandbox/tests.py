import json

import pytest
from channels.testing import WebsocketCommunicator

from apps.sandbox.consumers import SandboxConsumer
from config.asgi import application


@pytest.mark.django_db
@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_sandbox_websocket_consumer():
    headers = [(b"origin", b"http://localhost"), (b"host", b"localhost")]
    communicator1 = WebsocketCommunicator(application, "/ws/sandbox/", headers=headers)
    connected1, _ = await communicator1.connect()
    assert connected1

    communicator2 = WebsocketCommunicator(application, "/ws/sandbox/", headers=headers)
    connected2, _ = await communicator2.connect()
    assert connected2

    await communicator1.send_json_to(
        {"action": "code_update", "code": "print('hello from 1')"}
    )

    response2 = await communicator2.receive_json_from()
    assert response2["action"] == "code_update"
    assert response2["code"] == "print('hello from 1')"

    # communicator1 should NOT receive it (no echo)
    assert await communicator1.receive_nothing()

    # Send message from communicator2
    await communicator2.send_json_to(
        {"action": "code_update", "code": "print('hello from 2')"}
    )

    # communicator1 should receive it
    response1 = await communicator1.receive_json_from()
    assert response1["action"] == "code_update"
    assert response1["code"] == "print('hello from 2')"

    # Test malformed JSON
    await communicator1.send_to(text_data="INVALID JSON STRING")
    # Should not crash and not broadcast anything
    assert await communicator2.receive_nothing()

    # Test unknown action
    await communicator1.send_json_to(
        {"action": "unknown_action", "code": "print('hello')"}
    )
    assert await communicator2.receive_nothing()

    # Test missing code field
    await communicator1.send_json_to({"action": "code_update"})
    response_missing = await communicator2.receive_json_from()
    assert response_missing["action"] == "code_update"
    assert response_missing["code"] is None

    # Test payload is a JSON list instead of dict
    await communicator1.send_to(text_data=json.dumps(["this is a list", "not a dict"]))
    assert await communicator2.receive_nothing()

    await communicator1.disconnect()
    await communicator2.disconnect()


def test_sandbox_security_ast_violations():
    from apps.sandbox.resource_manager import (
        ResourceManagementEngine,
        SecurityViolation,
    )

    # Test dynamic lookup / builtin function assignment
    with pytest.raises(SecurityViolation):
        ResourceManagementEngine.analyze_ast("my_getattr = getattr")

    # Test magic double underscore attribute access
    with pytest.raises(SecurityViolation):
        ResourceManagementEngine.analyze_ast("().__class__.__base__")

    # Test double underscore string literal
    with pytest.raises(SecurityViolation):
        ResourceManagementEngine.analyze_ast("x = '__class__'")

    # Test normal code works
    ResourceManagementEngine.analyze_ast("x = 10\nprint(x)")


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_collab_websocket_consumer():
    import uuid

    room_id = str(uuid.uuid4())
    headers = [(b"origin", b"http://localhost"), (b"host", b"localhost")]

    communicator1 = WebsocketCommunicator(
        application, f"/ws/collab/{room_id}/", headers=headers
    )
    connected1, _ = await communicator1.connect()
    assert connected1

    # Send binary update from communicator1
    test_update = b"yjs-test-update-bytes"
    await communicator1.send_to(bytes_data=test_update)

    # Disconnect to trigger save
    await communicator1.disconnect()

    # Reconnect and connect a second client
    communicator1 = WebsocketCommunicator(
        application, f"/ws/collab/{room_id}/", headers=headers
    )
    connected1, _ = await communicator1.connect()
    assert connected1

    # Handshake: communicator1 should receive the stored state
    response_handshake = await communicator1.receive_from()
    assert response_handshake == test_update

    communicator2 = WebsocketCommunicator(
        application, f"/ws/collab/{room_id}/", headers=headers
    )
    connected2, _ = await communicator2.connect()
    assert connected2

    # Late joiner handshake: communicator2 should also receive the stored state
    response_handshake2 = await communicator2.receive_from()
    assert response_handshake2 == test_update

    # communicator2 sends additional update
    test_update2 = b"more-yjs-bytes"
    await communicator2.send_to(bytes_data=test_update2)

    # communicator1 should receive the broadcasted update
    response_broadcast = await communicator1.receive_from()
    assert response_broadcast == test_update2

    # Disconnect both to finalize persistence
    await communicator1.disconnect()
    await communicator2.disconnect()

    # Verify document_state in the database
    from apps.sandbox.models import CollabSession
    from channels.db import database_sync_to_async

    @database_sync_to_async
    def check_db():
        session = CollabSession.objects.filter(id=room_id).first()
        return (
            bytes(session.document_state)
            if session and session.document_state
            else None
        )

    db_state = await check_db()
    assert db_state == test_update + test_update2
