"""
Admin WebSocket endpoint: /ws/admin?key={admin_key}

Responsibilities:
- Validate admin key on connect
- Accept/reject connection
- Route status updates to admin dashboard
- No game logic
"""

import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from .manager import manager
from .events import build_error, build_event, PONG, PING
from ..config import settings

logger = logging.getLogger("ws.admin")
router = APIRouter()


@router.websocket("/ws/admin")
async def admin_websocket(
    websocket: WebSocket,
    key: str = Query(...)
):
    # ── 1. Validate admin key ──────────────────────────────────────────────
    if key != settings.admin_key:
        await websocket.close(code=4003, reason="Invalid admin key")
        return

    # ── 2. Register admin connection ───────────────────────────────────────
    await manager.connect_admin(websocket)

    try:
        # Send confirmation
        await websocket.send_json(build_event("ADMIN_CONNECTED", {"status": "ok"}))

        # ── 3. Message loop ────────────────────────────────────────────────
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json(
                    build_error("INVALID_JSON", "Message must be valid JSON")
                )
                continue

            event_type = message.get("event")

            if event_type == PING:
                await websocket.send_json(build_event(PONG, {}))
            else:
                # Admin control events (START, RESET, etc.) handled in Chunk 4+
                await websocket.send_json(
                    build_error("UNKNOWN_EVENT", f"Event '{event_type}' not handled yet")
                )

    except WebSocketDisconnect:
        await manager.disconnect_admin()
    except Exception as e:
        logger.error(f"Admin WS error: {e}")
        await manager.disconnect_admin()
