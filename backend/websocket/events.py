"""
Single source of truth for all WebSocket event names and payload builders.
No game logic here — just event shape definitions.
"""

# ─── Server → Client Events ───────────────────────────────────────────────────

SHOW_PROBLEMS = "SHOW_PROBLEMS"
SELECTION_UPDATE = "SELECTION_UPDATE"
START_PART_A = "START_PART_A"
TIMER_TICK = "TIMER_TICK"
LOCK_AND_SUBMIT = "LOCK_AND_SUBMIT"
WAIT_FOR_SWAP = "WAIT_FOR_SWAP"
START_PART_B = "START_PART_B"
RESULT = "RESULT"
SESSION_RESTORE = "SESSION_RESTORE"
ERROR = "ERROR"
PONG = "PONG"
CONNECTED = "CONNECTED"
PARTNER_JOINED = "PARTNER_JOINED"

# ─── Client → Server Events ───────────────────────────────────────────────────

CHOOSE_PROBLEM = "CHOOSE_PROBLEM"
DRAFT_SAVE = "DRAFT_SAVE"
FINAL_SUBMIT = "FINAL_SUBMIT"
PING = "PING"

# ─── Admin Events ─────────────────────────────────────────────────────────────

ADMIN_STATUS_UPDATE = "ADMIN_STATUS_UPDATE"
ADMIN_TEAM_UPDATE = "ADMIN_TEAM_UPDATE"


# ─── Payload Builders ─────────────────────────────────────────────────────────

def build_event(event_type: str, data: dict = None) -> dict:
    """Standard envelope for all WS messages."""
    return {"event": event_type, "data": data or {}}


def build_error(code: str, message: str, retry: bool = False) -> dict:
    return build_event(ERROR, {"code": code, "message": message, "retry": retry})


def build_connected(player_id: int, team_id: str, player_name: str) -> dict:
    return build_event(CONNECTED, {
        "player_id": player_id,
        "team_id": team_id,
        "player_name": player_name,
    })


def build_partner_joined(partner_name: str) -> dict:
    return build_event(PARTNER_JOINED, {"partner_name": partner_name})


def build_show_problems(problems: list) -> dict:
    return build_event(SHOW_PROBLEMS, {"problems": problems})


def build_session_restore(phase: str, data: dict) -> dict:
    return build_event(SESSION_RESTORE, {"phase": phase, **data})


def build_pong() -> dict:
    return build_event(PONG, {})


def build_admin_status(teams: list) -> dict:
    return build_event(ADMIN_STATUS_UPDATE, {"teams": teams})
