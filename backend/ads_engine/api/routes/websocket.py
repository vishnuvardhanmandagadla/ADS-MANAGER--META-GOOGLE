"""WebSocket endpoint — real-time updates to the dashboard.

Clients connect to /ws and receive JSON events whenever:
  - A new action is queued (action_queued)
  - An action is approved (action_approved)
  - An action is rejected (action_rejected)
  - An action is executed (action_executed)
  - An action fails (action_failed)

The ConnectionManager is a singleton imported by other modules to broadcast events.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """Manages all active WebSocket connections and broadcasts events."""

    def __init__(self):
        # client_id → list of WebSocket connections (None = all clients)
        self._connections: list[tuple[WebSocket, Optional[str]]] = []

    async def connect(self, websocket: WebSocket, client_id: Optional[str] = None) -> None:
        await websocket.accept()
        self._connections.append((websocket, client_id))
        logger.info(
            "WS connected: %s (filter=%s) — %d total",
            websocket.client, client_id, len(self._connections),
        )

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections = [(ws, cid) for ws, cid in self._connections if ws != websocket]
        logger.info("WS disconnected — %d remaining", len(self._connections))

    async def broadcast(self, event: str, data: dict, client_id: Optional[str] = None) -> None:
        """Send an event to all relevant connections.

        Args:
            event: Event name (e.g. "action_queued")
            data: Event payload dict
            client_id: If set, only send to connections subscribed to this client
                       (or connections with no filter = receive everything)
        """
        message = json.dumps({
            "event": event,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        dead: list[WebSocket] = []
        for ws, filter_cid in self._connections:
            # Send if: no filter on connection, no filter on event, or filters match
            if filter_cid is None or client_id is None or filter_cid == client_id:
                try:
                    await ws.send_text(message)
                except Exception:
                    dead.append(ws)

        # Clean up dead connections
        for ws in dead:
            self.disconnect(ws)

    async def send_ping(self) -> None:
        """Keep connections alive."""
        await self.broadcast("ping", {"status": "ok"})

    @property
    def connection_count(self) -> int:
        return len(self._connections)


# Singleton — import this in routes that need to broadcast
ws_manager = ConnectionManager()


# ── WebSocket endpoint ─────────────────────────────────────────────────────────


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: Optional[str] = None,
):
    """Connect to receive real-time dashboard events.

    Query params:
        client_id: Optional filter — only receive events for this client
    """
    await ws_manager.connect(websocket, client_id)

    # Send welcome message with current connection count
    await websocket.send_text(json.dumps({
        "event": "connected",
        "data": {
            "message": "Connected to Ads Engine real-time feed",
            "client_filter": client_id,
            "connections": ws_manager.connection_count,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }))

    try:
        while True:
            # Keep connection alive — client can send pings
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text(json.dumps({
                    "event": "pong",
                    "data": {},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }))
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
