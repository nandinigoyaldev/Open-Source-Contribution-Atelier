import json

import pytest
from apps.sandbox.consumers import SandboxConsumer
from channels.testing import WebsocketCommunicator
from config.asgi import application



@pytest.mark.asyncio
async def test_sandbox_websocket_consumer():
    headers = [(b"origin", b"http://localhost"), (b"host", b"localhost")]
    communicator1 = WebsocketCommunicator(application, "/ws/sandbox/", headers=headers)
    connected1, _ = await communicator1.connect()
    assert connected1

    communicator2 = WebsocketCommunicator(application, "/ws/sandbox/", headers=headers)
    connected2, _ = await communicator2.connect()
    assert connected2

    # Send message from communicator1
    await communicator1.send_json_to(
        {"action": "code_update", "code": "print('hello from 1')"}
    )

    # communicator2 should receive it
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
