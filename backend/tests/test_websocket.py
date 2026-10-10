import pytest
from starlette.websockets import WebSocketDisconnect
from backend.app.auth.security import create_access_token


def test_websocket_unauthenticated_rejected(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/dashboard") as ws:
            pass


def test_websocket_authenticated_connect_and_ping(client, test_user):
    token = create_access_token(data={"sub": test_user.id, "username": test_user.username, "is_admin": test_user.is_admin})

    with client.websocket_connect(f"/ws/dashboard?token={token}") as ws:
        ws.send_text("ping")
        data = ws.receive_text()
        assert "pong" in data
