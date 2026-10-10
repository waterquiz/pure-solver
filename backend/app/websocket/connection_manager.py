import json
from typing import Dict, List, Set
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        # Maps user_id -> Set of active WebSocket connections
        self._user_connections: Dict[str, Set[WebSocket]] = {}
        # Tracks admin user IDs
        self._admin_user_ids: Set[str] = set()

    async def connect(self, websocket: WebSocket, user_id: str, is_admin: bool = False):
        await websocket.accept()
        if user_id not in self._user_connections:
            self._user_connections[user_id] = set()
        self._user_connections[user_id].add(websocket)
        if is_admin:
            self._admin_user_ids.add(user_id)

    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self._user_connections:
            self._user_connections[user_id].discard(websocket)
            if not self._user_connections[user_id]:
                del self._user_connections[user_id]
                self._admin_user_ids.discard(user_id)

    async def send_to_user(self, user_id: str, message: dict):
        """Sends message to all connections belonging to a specific user."""
        if user_id in self._user_connections:
            payload = json.dumps(message)
            dead_connections = []
            for ws in list(self._user_connections[user_id]):
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead_connections.append(ws)
            for ws in dead_connections:
                self._user_connections[user_id].discard(ws)

    async def broadcast_image_event(self, owner_user_id: str, event_type: str, image_data: dict):
        """
        Broadcasts an image event (image_received, image_deleted) only to:
        1. The user who owns the image / API key
        2. Any connected admin users
        """
        message = {
            "type": event_type,
            "data": image_data
        }
        if event_type == "all_images_cleared":
            for uid in list(self._user_connections.keys()):
                await self.send_to_user(uid, message)
            return

        # Collect target users: owner + all connected admins
        target_users = {owner_user_id}.union(self._admin_user_ids)
        for uid in target_users:
            await self.send_to_user(uid, message)

    def has_active_connections(self, owner_user_id: str = None) -> bool:
        """Returns True if there is an active WebSocket dashboard connection listening."""
        if owner_user_id:
            return bool(self._user_connections.get(owner_user_id) or self._admin_user_ids)
        return bool(self._user_connections)


manager = ConnectionManager()

