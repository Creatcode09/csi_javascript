"""
ConnectionManager — team-based WebSocket registry.
Validates session tokens on connect. Provides broadcast-to-team and send-to-player.
"""

import json
import logging
import aiosqlite
from fastapi import WebSocket
from ..config import settings

logger = logging.getLogger("ws.manager")


class ConnectionManager:
    """
    Manages active WebSocket connections indexed by team_id → player_id.
    Also tracks the admin connection separately.
    """

    def __init__(self):
        # { team_id: { player_id: WebSocket } }
        self._teams: dict[str, dict[int, WebSocket]] = {}
        self._admin_ws: WebSocket | None = None

    # ── Session Validation ─────────────────────────────────────────────────

    async def validate_session(self, team_id: str, player_id: int, token: str) -> bool:
        """
        Check that (player_id, team_id, session_token) exist together in the DB.
        Called on every WS connect attempt.
        """
        async with aiosqlite.connect(settings.database_path) as db:
            async with db.execute(
                "SELECT id FROM players WHERE id = ? AND team_id = ? AND session_token = ?",
                (player_id, team_id, token)
            ) as cursor:
                return await cursor.fetchone() is not None

    # ── Player Connections ─────────────────────────────────────────────────

    async def connect_player(self, team_id: str, player_id: int, ws: WebSocket):
        await ws.accept()
        if team_id not in self._teams:
            self._teams[team_id] = {}
        self._teams[team_id][player_id] = ws

        # Update connection status in DB
        async with aiosqlite.connect(settings.database_path) as db:
            await db.execute(
                "UPDATE players SET connection_status = 'online' WHERE id = ? AND team_id = ?",
                (player_id, team_id)
            )
            await db.commit()

        logger.info(f"Player {player_id} connected to team {team_id}")

    async def disconnect_player(self, team_id: str, player_id: int):
        if team_id in self._teams:
            self._teams[team_id].pop(player_id, None)
            if not self._teams[team_id]:
                del self._teams[team_id]

        # Update connection status in DB
        async with aiosqlite.connect(settings.database_path) as db:
            await db.execute(
                "UPDATE players SET connection_status = 'offline' WHERE id = ? AND team_id = ?",
                (player_id, team_id)
            )
            await db.commit()

        logger.info(f"Player {player_id} disconnected from team {team_id}")

    # ── Admin Connection ───────────────────────────────────────────────────

    async def connect_admin(self, ws: WebSocket):
        await ws.accept()
        self._admin_ws = ws
        logger.info("Admin connected")

    async def disconnect_admin(self):
        self._admin_ws = None
        logger.info("Admin disconnected")

    # ── Queries ────────────────────────────────────────────────────────────

    def get_team_connections(self, team_id: str) -> dict[int, WebSocket]:
        return self._teams.get(team_id, {})

    def get_team_player_count(self, team_id: str) -> int:
        return len(self._teams.get(team_id, {}))

    def is_team_full(self, team_id: str) -> bool:
        """Both players in the team are connected via WS."""
        return self.get_team_player_count(team_id) == 2

    def is_player_connected(self, team_id: str, player_id: int) -> bool:
        return player_id in self._teams.get(team_id, {})

    # ── Sending ────────────────────────────────────────────────────────────

    async def send_to_player(self, team_id: str, player_id: int, message: dict):
        conns = self._teams.get(team_id, {})
        ws = conns.get(player_id)
        if ws:
            try:
                await ws.send_json(message)
            except Exception:
                logger.warning(f"Failed to send to player {player_id} in team {team_id}")

    async def broadcast_to_team(self, team_id: str, message: dict, exclude_player: int = None):
        conns = self._teams.get(team_id, {})
        for pid, ws in conns.items():
            if pid == exclude_player:
                continue
            try:
                await ws.send_json(message)
            except Exception:
                logger.warning(f"Failed to broadcast to player {pid} in team {team_id}")

    async def send_to_admin(self, message: dict):
        if self._admin_ws:
            try:
                await self._admin_ws.send_json(message)
            except Exception:
                logger.warning("Failed to send to admin")


# Singleton instance used across the app
manager = ConnectionManager()
