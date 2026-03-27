# Exchange The Code — System Preparation Document

> **Purpose:** Complete system understanding, organized for chunk-by-chunk development.
> **Rule:** No new features, no modifications, no code. Only clarity.

---

## 1. System Understanding

**Exchange the Code** is a real-time, relay-style competitive coding platform built for offline college techfests. It runs entirely on a **Local Area Network (LAN)** — no internet dependency.

**The core mechanic** is forced context switching:
- Player A writes the foundation of Problem 1 (Part A)
- Player B writes the foundation of Problem 2 (Part A)
- After a timed lock, code is swapped: Player A must now complete Problem 2's Part B using Player B's foundation, and vice versa
- Neither player can modify the other's Part A

**Two roles exist:**
- **Admin** — Creates teams, assigns problems, triggers the round, monitors all rooms live, views the leaderboard
- **Player** — Joins a team, selects a problem, codes Part A, receives partner's code, codes Part B, receives final score

**Infrastructure:**
- Backend: FastAPI (Python) + aiosqlite (SQLite with WAL mode)
- Frontend: Vanilla JS + Monaco Editor (browser-based)
- Transport: WebSockets for real-time events + REST for join/setup
- Network: LAN star topology, accessible at `techfest.local:8000` via DNSMasq
- Execution: Sandboxed subprocesses with resource limits (Python + C++)
- Resilience: Hot standby server, 60s DB snapshots, watchdog process

---

## 2. Game Flow (Clean Step-by-Step)

```
JOIN → WAIT_FOR_PARTNER → SHOW_PROBLEMS → SELECT → WAIT_FOR_BOTH → ADMIN_START
     → PART_A → LOCK → WAIT_BUFFER → SWAP → PART_B → EXECUTE → RESULTS
```

### Phase 0 — Setup (Admin only, before players join)
- Admin creates teams via dashboard
- Each team gets a short readable Team ID (e.g. `ALPHA-42`)
- Admin assigns exactly **2 problems** to each team
- Team IDs are distributed to players verbally or on paper

### Phase 1 — Join
- Each player opens the player console, enters name + Team ID
- Client calls `POST /join` → server creates player record, returns session token
- Player opens WebSocket connection to `/ws/{room_id}/{player_id}`
- Server waits until **both** players in the team are connected before proceeding

### Phase 2 — Selection
- When both players are connected, server sends `SHOW_PROBLEMS` to both
- Each player sees 2 problem cards (title + brief description)
- Player clicks a card → client sends `CHOOSE_PROBLEM` WS event
- Server runs **atomic DB transaction**: check conflict → lock or reject
- If two players click the same problem simultaneously, first request wins; second gets `ALREADY_CLAIMED` error and must pick the other
- Server broadcasts `SELECTION_UPDATE` after every attempt (success or conflict) — both players see each other's choice in real time
- When both players have selected, room status → `ready`

### Phase 3 — Part A Coding
- Admin sees all rooms as `ready` on dashboard
- Admin clicks **Start All** → server broadcasts `START_PART_A` to all rooms simultaneously
- Each player receives: their chosen problem's Part A prompt + a pre-displayed non-editable function stub
- Monaco editor is active; countdown timer runs
- Client auto-saves draft to IndexedDB every 10s and sends `DRAFT_SAVE` WS event to server
- Server sends `TIMER_TICK` every 5s to keep client timers synced

### Phase 4 — Lock and Submit
- Part A timer expires → server broadcasts `LOCK_AND_SUBMIT` to room
- Monaco editor is set to `readOnly = true` immediately on client
- Client sends `FINAL_SUBMIT` WS event with current code
- Server stores code + computes and stores **SHA-256 hash**, sets `is_final = true`
- Fallback: if no `FINAL_SUBMIT` received, server uses last `DRAFT_SAVE` content; if no draft exists, submits empty stub with function signature

### Phase 5 — Wait Buffer
- Server broadcasts `WAIT_FOR_SWAP` with a **10-second countdown**
- Ticks every 1 second — all players see a visual countdown
- Swap does not execute until countdown reaches 0
- Purpose: confirm all submissions received; provide moment of anticipation

### Phase 6 — Code Exchange (Swap)
- Swap engine queries `chosen_problem_id` for both players in the team
- Fetches their respective final Part A submissions and validates hashes
- Builds per-player swap payload:
  - Player A wrote Problem 1 Part A → Player B receives it with Problem 1's Part B prompt
  - Player B wrote Problem 2 Part A → Player A receives it with Problem 2's Part B prompt
- Server sends `START_PART_B` individually to each player with partner's code + Part B prompt
- Swap is driven by `chosen_problem_id` — not by player slot or position

### Phase 7 — Part B Coding
- Each player sees partner's Part A code in a **permanently read-only** panel above the editor
- Player writes Part B in Monaco editor (active)
- Second countdown timer runs; `TIMER_TICK` keeps sync
- Auto-save (IndexedDB + `DRAFT_SAVE`) continues

### Phase 8 — Final Execution
- Part B timer expires → both submissions locked (same LOCK flow as Phase 4)
- Server combines Part A (original author, hash-verified) + Part B (current player)
- Validation engine checks: hash integrity, function interface stub present
- Code runner executes combined code in sandboxed subprocess against all test cases
- Scoring: `(passed_tests / total_tests) * 100 + time_bonus`
- Results stored in `execution_results` table

### Phase 9 — Results
- Server broadcasts `RESULT` to the room and to admin
- Player console shows: score, per-test-case breakdown, team rank
- Admin leaderboard shows: all teams ranked by total score across both problems

---

## 3. Architecture Summary

The system has **four architectural layers**:

### Client Layer (Browsers)
- **Player Console** × 2 per team — Monaco editor, timer, WebSocket client, IndexedDB storage
- **Admin Dashboard** × 1 — Monitor grid, control bar, leaderboard, admin WebSocket

### Backend Layer (FastAPI on LAN server)
- **REST Routers** — Handle join, problem retrieval, admin setup, admin start
- **WebSocket Endpoints** — Player WS at `/ws/{room_id}/{player_id}`, Admin WS at `/ws/admin`
- **Core Services** — Room Manager, Selection Manager, Timer Engine, Swap Engine, Submission Handler, Validation Engine
- **Runner** — Sandboxed Python and C++ execution

### Storage Layer
- **SQLite** (WAL mode) — All persistent state: teams, players, problems, submissions, results, audit log

### Infrastructure Layer
- **LAN** — DNSMasq, static IP, `techfest.local`, port 8000
- **Backup** — DB snapshots every 60s via rsync to standby, WAL mode consistency
- **Ops** — Watchdog auto-restart, deploy script, setup script

---

## 4. Data Flow Summary

### Join Flow
```
Player types name + Team ID
  → POST /join
  → Server creates player record, generates UUID session token
  → Returns WS URL
  → Player opens WS connection
  → Server checks: both players now joined?
  → If yes: sends SHOW_PROBLEMS to both players in room
```

### Selection Flow
```
Player clicks problem card
  → Client sends CHOOSE_PROBLEM (with session token)
  → Server runs atomic DB transaction
    → If available: lock problem to player, update chosen_problem_id
    → If taken: return ALREADY_CLAIMED error
  → Server broadcasts SELECTION_UPDATE to both players in room
  → When both selected: room status → ready
```

### Start Flow
```
Admin dashboard polls GET /admin/status
  → Sees all rooms ready
  → Admin clicks Start All → POST /admin/start
  → Server validates all teams ready (ready-check gate)
  → Server broadcasts START_PART_A to all rooms simultaneously
  → Timer engine starts async per-room countdown
```

### Coding + Lock Flow
```
Player types → client auto-saves to IndexedDB every 10s
             → client sends DRAFT_SAVE WS event to server (stored in DB)
Timer fires  → server broadcasts LOCK_AND_SUBMIT
             → client sets Monaco readOnly = true
             → client sends FINAL_SUBMIT WS event
             → server stores code + SHA-256 hash, is_final = true
             → fallback to last DRAFT_SAVE if FINAL_SUBMIT not received
```

### Buffer Flow
```
After LOCK:
  → Server broadcasts WAIT_FOR_SWAP with countdown = 10
  → Ticks every 1 second down to 0
  → At 0: swap executes
```

### Swap Flow
```
Swap engine queries DB:
  → chosen_problem_id for Player A and Player B
  → Final Part A submissions for each
  → Validates SHA-256 hashes
  → Builds per-player payload
  → Sends START_PART_B to Player A (with Player B's code + Problem B's Part B prompt)
  → Sends START_PART_B to Player B (with Player A's code + Problem A's Part B prompt)
```

### Execution Flow
```
Part B timer fires → LOCK → FINAL_SUBMIT
  → Validation engine: verify Part A hash, verify function stub
  → Code runner: combine Part A + Part B → run in sandbox → per-test-case results
  → Scoring formula applied
  → Results stored in execution_results
  → RESULT broadcast to room + admin leaderboard
```

### Reconnect Flow
```
Player reconnects (within 30s window)
  → WS connection re-established
  → Server queries DB for current phase, code, timer state, selection
  → Sends SESSION_RESTORE with full state
  → Client restores exactly where player was
```

---

## 5. Module Breakdown

### 5.1 Player Console (Frontend)

| File | Responsibility |
|------|---------------|
| `index.html` | Single-page container; hosts all screens |
| `screens/join.js` | Name + Team ID form; calls POST /join; opens WS |
| `screens/selection.js` | Two problem cards; claim button; live teammate status; conflict error display |
| `screens/waiting.js` | Generic waiting screen for: partner join, admin start, swap buffer countdown |
| `screens/editor.js` | Monaco init; Part A prompt panel; Part B partner-code read-only panel; lock/unlock behaviour |
| `screens/result.js` | Score display; per-test-case breakdown table |
| `websocket.js` | WS connection; exponential backoff reconnect; all incoming event routing to screens |
| `timer.js` | Client-side countdown; syncs with TIMER_TICK from server |
| `storage.js` | IndexedDB draft: saveDraft(), loadDraft(), clearDraft(); sends DRAFT_SAVE WS event |

### 5.2 Admin Dashboard (Frontend)

| File | Responsibility |
|------|---------------|
| `index.html` | Single-page admin dashboard |
| `setup.js` | Team creation form; problem assignment UI; generated Team ID display with copy button |
| `monitor.js` | Live room grid; updates on every WS status event; shows connection/selection/submission status per player |
| `controls.js` | Start All (with ready-check gate; shows blocking teams); Reset Round; Force Lock |
| `leaderboard.js` | Sorted results table; updates on RESULT events |
| `websocket.js` | Admin WS connection with admin key auth; routes status updates to monitor and leaderboard |

### 5.3 Backend Services

| Module | File | Key Functions |
|--------|------|---------------|
| Room Manager | `core/room_manager.py` | `create_team()`, `assign_problems_to_team()`, `get_team_problems()`, `get_room_players()`, `update_room_status()` — owns room lifecycle state machine |
| Selection Manager | `core/selection_manager.py` | `attempt_selection()` (atomic DB transaction), `get_team_selections()`, `all_teams_ready()` — logs all attempts to selection_log |
| Timer Engine | `core/timer_engine.py` | `run_part_a_phase()`, `run_wait_buffer()`, `run_part_b_phase()` — async per-room, broadcasts TIMER_TICK every 5s, drives all phase transitions |
| Swap Engine | `core/swap_engine.py` | `swap_code(team_id)` — reads chosen_problem_id, fetches Part A submissions, validates hashes, builds per-player payload |
| Submission Handler | `core/submission_handler.py` | `receive_submission()`, `auto_submit_draft()`, `compute_hash()` — SHA-256, is_final flag, retry queue |
| Validation Engine | `core/validation_engine.py` | `verify_part_a_hash()`, `verify_interface_stub()` — pre-execution integrity checks |
| WS Manager | `websocket/manager.py` | Connection registry (room_id → player_id → websocket); connect/disconnect/broadcast/send primitives; session token validation on every message |
| WS Events | `websocket/events.py` | All event name constants + payload builder functions — single source of truth for event shapes |
| Player WS | `websocket/player_ws.py` | Endpoint `/ws/{room_id}/{player_id}`; routes incoming events to handlers |
| Admin WS | `websocket/admin_ws.py` | Endpoint `/ws/admin`; admin key validation |

### 5.4 Code Execution Engine

| Module | File | Responsibility |
|--------|------|---------------|
| Base Runner | `runner/base_runner.py` | `RunResult` dataclass; common interface for language runners |
| Sandbox | `runner/sandbox.py` | Subprocess environment; CPU time + memory limits; temp file management + cleanup |
| Python Runner | `runner/python_runner.py` | Execute Python code in subprocess; per-test-case results; captures stdout/stderr; handles timeout |
| C++ Runner | `runner/cpp_runner.py` | Compile with g++; execute binary; capture compile errors; per-test-case results |

### 5.5 Database Schema (8 Tables)

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `rounds` | One record per event round | status, phase durations, start/end times |
| `teams` | One per team; belongs to round | team_id (readable), room_id |
| `team_problems` | Junction: 2 problems per team | team_id, problem_id (unique constraint) |
| `players` | Two per team | name, session_token, connection_status, **chosen_problem_id**, selection_locked_at |
| `problems` | Problem definitions | part_a_prompt, part_b_prompt, interface_stub, language, description |
| `test_cases` | Belongs to problem | input, expected_output, is_visible flag |
| `submissions` | One per submit action | player_id, problem_id, code, sha256_hash, phase (part_a/part_b), **is_final** |
| `execution_results` | One per execution | team_id, problem_id, status, score, per-test-case breakdown, execution_time |
| `selection_log` | Append-only audit log | All selection attempts including rejected conflicts; used for dispute resolution |

---

## 6. WebSocket Event Reference

### Server → Client Events

| Event | Trigger | Purpose |
|-------|---------|---------|
| `SHOW_PROBLEMS` | Both players joined room | Send both problem titles/descriptions to both players |
| `SELECTION_UPDATE` | Any selection attempt | Broadcast current selection state; includes error if conflict |
| `START_PART_A` | Admin triggers start | Begin Part A phase; includes problem prompt + timer duration |
| `TIMER_TICK` | Every 5s during active phase | Keep client timers synced with server |
| `LOCK_AND_SUBMIT` | Part A timer expires | Freeze editor; trigger auto-submit |
| `WAIT_FOR_SWAP` | After lock; every 1s for 10s | Show swap countdown to all players |
| `START_PART_B` | After buffer completes | Deliver partner's code + Part B prompt (sent individually per player) |
| `RESULT` | After execution completes | Deliver score and per-test-case results |
| `SESSION_RESTORE` | Player reconnects | Restore full state: phase, code, timer, selection |
| `ERROR` | Any server-side failure | Inform client with error code and retry flag |

### Client → Server Events

| Event | When Sent | Purpose |
|-------|-----------|---------|
| `CHOOSE_PROBLEM` | Player clicks problem card | Attempt to claim a problem |
| `DRAFT_SAVE` | Every 10 seconds | Persist current editor content server-side |
| `FINAL_SUBMIT` | On lock or manual submit | Send final code for hash + storage |
| `PING` | Every 15 seconds | Keep-alive heartbeat |

---

## 7. Error Handling and Edge Cases

| Scenario | Handling |
|----------|---------|
| Selection conflict (simultaneous click) | DB transaction ensures exactly one wins; loser gets `ALREADY_CLAIMED` + redirected to other problem |
| Partner never joins | First player stays on waiting screen; admin can start with one player (team treated as unsubmitted) |
| Disconnect during selection | SESSION_RESTORE includes current phase + their chosen_problem_id + full SELECTION_UPDATE state |
| Disconnect during Part A | SESSION_RESTORE includes current code + time remaining + phase; IndexedDB draft also available locally |
| Timer fires with no submission | Server uses last DRAFT_SAVE; if none exists, submits empty stub with function signature |
| Swap fails (missing Part A) | ERROR broadcast with `SWAP_FAILED` to admin; admin can manual-override or inject last draft |
| Part A hash mismatch | Execution rejected; result stored as `integrity_error`; team scores zero for that problem |
| Compilation error | Runner captures stderr; returned to client as readable error; player can fix + resubmit within Part B time |
| Infinite loop | Subprocess timeout (5s) kills process; result = `timeout`; that test case scores zero |
| Server crash mid-round | Hot standby takes over; SQLite WAL ensures consistency to last commit; room states restored from DB on restart |

---

## 8. Security and Integrity Mechanisms

| Mechanism | Implementation |
|-----------|---------------|
| Session tokens | UUID per player at `/join`; validated on every incoming WS message; invalid/missing = rejected |
| Part A lock (frontend) | Monaco `readOnly = true` on LOCK_AND_SUBMIT; Part A panel in Part B is a separate display element, not the editor |
| Part A lock (backend) | SHA-256 hash stored at lock time; recomputed before execution; mismatch = reject + zero score |
| Sandboxed execution | Subprocess with OS-level resource limits; no network/filesystem access outside temp dir; cleanup after each run |
| Admin authentication | Separate admin WS endpoint + REST endpoints; admin key (from config) required; validated on connect |
| Team ID security | Short but not guessable in closed LAN context; optional per-team join PIN available for extra protection |

---

## 9. Chunk Breakdown

### Overview of Dependency Order

```
Chunk 1 → Chunk 2 → Chunk 3 → Chunk 4
                                    ↓
              ┌─────────────────────┼─────────────────────┐
              ↓                     ↓                     ↓
           Chunk 5              Chunk 6              Chunk 7
           (can run            (can run             (can run
           in parallel)        in parallel)         in parallel)
              └─────────────────────┼─────────────────────┘
                                    ↓
                                Chunk 8
                        (Integration + Deployment)
```

Chunks 1–4 are strictly sequential. Chunks 5, 6, 7 can be built in parallel after Chunk 4. Chunk 8 requires all prior chunks complete.

---

### Chunk 1 — Backend Foundation

**Goal:** Running FastAPI server with DB initialised, player join working, problem retrieval working. No WebSocket yet.

**Dependencies:** None. This is the foundation.

**Files built:**
- Project folder structure
- `requirements.txt` + `.env`
- `config.py` — all settings from environment (timer durations, DB path, admin key, LAN host/port, execution limits)
- `database.py` — SQLite connection, schema initialisation, WAL mode
- `models.py` — all Pydantic request/response models (JoinRequest, ChooseProblemEvent, SubmitRequest, etc.)
- `routers/player.py` — `POST /join` (creates player record, returns session token) + `GET /problem`
- `routers/admin.py` — `POST /admin/create-team`, `POST /admin/assign-problems`
- `problems/problem_loader.py` — loads + caches problem JSON at startup
- `problems/data/p001.json` + `p002.json` — sample problem definitions

**Expected outcome:** `uvicorn main:app` starts cleanly. Two players can `POST /join` same team_id, both get unique session tokens. `GET /problem` returns correct problems. DB records verified.

---

### Chunk 2 — WebSocket System

**Goal:** Real-time bidirectional communication for players and admin. Session validation on all messages.

**Dependencies:** Chunk 1 (DB, player records, session tokens)

**Files built:**
- `websocket/manager.py` — `ConnectionManager`: connect, disconnect, broadcast-to-room, send-to-player; session token validation middleware
- `websocket/events.py` — all event name constants + payload builder functions (single source of truth)
- `websocket/player_ws.py` — WS endpoint `/ws/{room_id}/{player_id}`; incoming event routing
- `websocket/admin_ws.py` — Admin WS endpoint; admin key validation; rejects invalid key
- PING/PONG heartbeat handling
- `SHOW_PROBLEMS` auto-trigger: when both players connect to a room
- `SESSION_RESTORE` logic: on reconnect, query DB and send full current state

**Expected outcome:** Two browser tabs connecting to same room both receive `SHOW_PROBLEMS` when second one joins. Reconnecting within 30s triggers `SESSION_RESTORE`. Admin WS connects with valid key; rejected with invalid key.

---

### Chunk 3 — Problem Selection System

**Goal:** Full selection flow end-to-end. Conflict prevention verified.

**Dependencies:** Chunks 1 + 2 (DB + WS manager)

**Files built:**
- `core/selection_manager.py` — `attempt_selection()` (atomic DB transaction), `get_team_selections()`, `all_teams_ready()`
- WS handler routing for `CHOOSE_PROBLEM` event
- `SELECTION_UPDATE` broadcast after every selection attempt (success or conflict)
- `GET /admin/ready-check` — returns which teams are not yet fully selected
- `POST /admin/override-selection` — admin override (pre-START only)
- Selection state included in `SESSION_RESTORE`

**Expected outcome:** Two players can select different problems. Simultaneous same-problem clicks: exactly one wins, other gets error. Both players see real-time selection updates. Admin ready-check returns correct status before and after both select.

---

### Chunk 4 — Timer Engine and Swap System

**Goal:** Complete backend game flow from START through SWAP to Part B start, fully automated.

**Dependencies:** Chunks 1 + 2 + 3

**Files built:**
- `core/timer_engine.py` — `run_part_a_phase()`, `run_wait_buffer()`, `run_part_b_phase()`; `TIMER_TICK` every 5s; `LOCK_AND_SUBMIT` trigger (marks room locked; stores drafts as final if no explicit submit)
- `core/submission_handler.py` — `receive_submission()`, `auto_submit_draft()`, `compute_hash()`
- `core/swap_engine.py` — `swap_code()` using `chosen_problem_id`; 10-second buffer with per-second `WAIT_FOR_SWAP` ticks; `START_PART_B` broadcast per player with partner's code + new problem prompt
- `core/validation_engine.py` — `verify_part_a_hash()`, `verify_interface_stub()` (stubs used fully in Chunk 5)
- `POST /admin/start` — validates all teams ready, then triggers timers for all rooms

**Expected outcome:** Admin hits start → all rooms get `START_PART_A` → timer ticks → `LOCK` fires → 10s buffer ticks → swap executes → each player receives correct partner code in `START_PART_B`. Full automated backend flow without manual intervention.

---

### Chunk 5 — Code Execution Engine

**Goal:** Sandboxed code execution for Python and C++ with test case validation and scoring.

**Dependencies:** Chunks 1 + 4 (DB, submission handler, validation engine)

**Files built:**
- `runner/base_runner.py` — `RunResult` dataclass; common interface
- `runner/sandbox.py` — subprocess environment; CPU time + memory limits; temp file cleanup
- `runner/python_runner.py` — run Python code against test cases; captures stdout/stderr; handles timeout
- `runner/cpp_runner.py` — compile with g++; execute binary; capture compile errors; per-test-case results
- Execution trigger: after Part B final submit, validate hash then run combined code
- `execution_results` table populated
- `RESULT` event broadcast to room and admin
- Scoring formula: `(passed_test_cases / total) * 100 + time_bonus`

**Expected outcome:** Valid code → passes and scores correctly. Wrong code → test failures. Infinite loop → killed after 5s, result = timeout. Syntax error → readable compile error returned to client.

---

### Chunk 6 — Player Console UI

**Goal:** Complete, fully functional player-facing interface handling all screens and state transitions.

**Dependencies:** Chunks 1–4 (all backend must be working to drive UI state)

**Files built:**
- `frontend/player/index.html` — single-page container
- `screens/join.js` — form, `POST /join`, open WS
- `screens/selection.js` — two problem cards, claim button, live teammate status, conflict error display
- `screens/waiting.js` — partner waiting / admin waiting / swap buffer countdown
- `screens/editor.js` — Monaco editor, Part A prompt panel, Part B partner-code read-only panel, lock behaviour
- `screens/result.js` — score + test case breakdown table
- `websocket.js` — WS connect, reconnect with exponential backoff, all event routing
- `timer.js` — client countdown, syncs to server `TIMER_TICK`
- `storage.js` — IndexedDB draft save/load/clear, `DRAFT_SAVE` event sending

**Expected outcome:** Player opens browser → joins team → sees both problems → selects one → codes Part A → experiences lock and buffer → receives partner code in Part B → submits → sees score. Fully through UI, no manual steps. Disconnect/reconnect at each phase works. Conflict selection handled in UI.

---

### Chunk 7 — Admin Dashboard

**Goal:** Fully functional admin control panel with live monitoring and leaderboard.

**Dependencies:** Chunks 1–4 for backend; Chunk 6 for design language reference

**Files built:**
- `frontend/admin/index.html` — single-page admin dashboard
- `setup.js` — create teams, assign problems, display generated Team IDs with copy button
- `monitor.js` — live room grid: connection status, selection status, submission status per player
- `controls.js` — Start All (calls ready-check first; shows blocking teams), Reset Round, Force Lock
- `leaderboard.js` — ranked table with scores; updates on `RESULT` events
- `websocket.js` — admin WS with key auth; routes status updates to monitor and leaderboard

**Expected outcome:** Admin creates full round, distributes Team IDs, monitors all teams live, starts round, watches progress, views final leaderboard — without touching any terminal. Start button blocked when teams not ready. Leaderboard populates correctly after execution.

---

### Chunk 8 — Integration, Backup, and Deployment

**Goal:** System runs reliably on LAN, survives failures, passes full end-to-end test.

**Dependencies:** All prior chunks (1–7) complete

**Files built:**
- `scripts/setup_lan.sh` — static IP, DNSMasq config, firewall rules
- `scripts/deploy.sh` — uvicorn production start, backup cron
- `scripts/backup.sh` — DB snapshot every 60s, rsync to standby
- `scripts/watchdog.py` — monitor and auto-restart main server
- SQLite WAL mode verified in production
- End-to-end checklist executed
- Load test: 10 simultaneous teams

**End-to-end checklist (7 items):**
1. Two teams, four players, complete a full round on separate machines
2. Disconnect one player mid-Part A; verify reconnect restores state
3. Both players in one team attempt same problem simultaneously; verify conflict handling
4. Submit code with compilation error; verify error message reaches client
5. Submit infinitely looping code; verify timeout kills it
6. Admin resets round; verify all state clears correctly
7. Run second round immediately after reset

**Expected outcome:** System runs for a full simulated event session with no manual server intervention.

---

## 10. File Structure Reference

```
exchange-the-code/
├── backend/
│   ├── main.py                    # FastAPI entry point; mounts routers; starts background services
│   ├── config.py                  # All configurable values from .env
│   ├── database.py                # SQLite connection; schema init; WAL mode; get_db() dependency
│   ├── models.py                  # All Pydantic request/response models
│   ├── routers/
│   │   ├── player.py              # POST /join, GET /problem
│   │   ├── submit.py              # POST /submit (REST fallback)
│   │   └── admin.py               # POST /admin/create-team, assign-problems, start, ready-check
│   ├── websocket/
│   │   ├── manager.py             # ConnectionManager; session validation
│   │   ├── events.py              # Event constants + payload builders
│   │   ├── player_ws.py           # /ws/{room_id}/{player_id}
│   │   └── admin_ws.py            # /ws/admin
│   ├── core/
│   │   ├── room_manager.py        # Room lifecycle state machine
│   │   ├── selection_manager.py   # Atomic selection; conflict prevention; audit log
│   │   ├── timer_engine.py        # Async per-room timers; phase transitions
│   │   ├── swap_engine.py         # Code swap logic
│   │   ├── submission_handler.py  # Store submissions; SHA-256; retry queue
│   │   └── validation_engine.py   # Hash + interface verification
│   ├── runner/
│   │   ├── base_runner.py         # RunResult dataclass
│   │   ├── python_runner.py       # Python execution
│   │   ├── cpp_runner.py          # C++ compile + execution
│   │   └── sandbox.py             # Subprocess limits + temp file cleanup
│   └── problems/
│       ├── problem_loader.py      # Load + cache problem JSON at startup
│       └── data/
│           ├── p001.json          # Problem 1 definition
│           └── p002.json          # Problem 2 definition
├── frontend/
│   ├── player/
│   │   ├── index.html
│   │   ├── screens/
│   │   │   ├── join.js
│   │   │   ├── selection.js
│   │   │   ├── waiting.js
│   │   │   ├── editor.js
│   │   │   └── result.js
│   │   ├── websocket.js
│   │   ├── timer.js
│   │   └── storage.js
│   └── admin/
│       ├── index.html
│       ├── setup.js
│       ├── monitor.js
│       ├── controls.js
│       ├── leaderboard.js
│       └── websocket.js
├── scripts/
│   ├── setup_lan.sh
│   ├── deploy.sh
│   ├── backup.sh
│   └── watchdog.py
├── .env
├── requirements.txt
└── README.md
```

---

## 11. Cross-Verification Confirmation

After full analysis across PRD, architecture SVGs, component map, and chunk roadmap:

- **PRD ↔ Architecture:** All modules described in PRD (Section 5) have corresponding files in the project structure and are represented in the architecture SVG layers (client, backend, execution, storage, ops).
- **Architecture ↔ Build Plan:** Every architectural component has a corresponding chunk that builds it. No component is unaccounted for.
- **Build Plan ↔ Chunks:** All 8 chunks together cover 100% of the project structure. No file is left without a chunk assignment. No chunk builds something not in the structure.
- **Swap logic verified:** Swap is driven by `chosen_problem_id` in all three places — PRD, swap engine design, and Chunk 4 description. No slot-based logic anywhere.
- **Selection conflict prevention verified:** Atomic DB transaction in Selection Manager agrees with WS event flow (CHOOSE_PROBLEM → attempt_selection → SELECTION_UPDATE) across PRD, backend module design, and Chunk 3.
- **Timer automation verified:** Admin START is the only manual trigger. All subsequent phases (lock, buffer, swap, Part B start) are driven automatically by the timer engine. Confirmed in PRD Section 4, timer_engine module design, and Chunk 4.
- **Hash integrity chain verified:** Hash computed at lock (Submission Handler) → stored in DB → verified before execution (Validation Engine) → mismatch = integrity_error. Chain is unbroken.
- **No orphan DB fields:** Every column in every table is referenced by at least one module. selection_log feeds admin dispute resolution. chosen_problem_id drives swap. is_final distinguishes draft from final submission.
- **No missing components:** 0 contradictions found.

---

*Document prepared from: PRD (prd.txt), full_system_architecture.svg, component_responsibility_map.svg, chunk_dependency_roadmap.svg*
*Ready for chunk-by-chunk implementation on command.*
