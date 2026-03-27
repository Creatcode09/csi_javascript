import aiosqlite
from .config import settings

async def get_db():
    db = await aiosqlite.connect(settings.database_path)
    # Enable WAL mode for high concurrency during locking/swapping
    await db.execute("PRAGMA journal_mode=WAL;")
    # Ensure foreign key constraints are enforced
    await db.execute("PRAGMA foreign_keys=ON;")
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()

async def init_db():
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        
        # Teams table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Problems table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS problems (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                part_a_prompt TEXT NOT NULL,
                part_b_prompt TEXT NOT NULL,
                interface_stub TEXT NOT NULL,
                language TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Team Problems junction table (Exactly 2 per team enforced at app level)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS team_problems (
                team_id TEXT NOT NULL,
                problem_id TEXT NOT NULL,
                FOREIGN KEY (team_id) REFERENCES teams (team_id) ON DELETE CASCADE,
                FOREIGN KEY (problem_id) REFERENCES problems (id) ON DELETE CASCADE,
                UNIQUE(team_id, problem_id)
            )
        """)
        
        # Players table (Team-based abstraction)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id TEXT NOT NULL,
                name TEXT NOT NULL,
                session_token TEXT UNIQUE NOT NULL,
                connection_status TEXT DEFAULT 'offline',
                chosen_problem_id TEXT,
                selection_locked_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (team_id) REFERENCES teams (team_id) ON DELETE CASCADE,
                FOREIGN KEY (chosen_problem_id) REFERENCES problems (id)
            )
        """)
        
        # Submissions table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER NOT NULL,
                problem_id TEXT NOT NULL,
                code TEXT NOT NULL,
                sha256_hash TEXT NOT NULL,
                phase TEXT NOT NULL, -- 'part_a' or 'part_b'
                is_final BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (player_id) REFERENCES players (id) ON DELETE CASCADE,
                FOREIGN KEY (problem_id) REFERENCES problems (id) ON DELETE CASCADE
            )
        """)
        
        # Execution Results table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS execution_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id TEXT NOT NULL,
                problem_id TEXT NOT NULL,
                status TEXT NOT NULL,
                score FLOAT NOT NULL,
                test_case_breakdown TEXT NOT NULL, -- JSON
                execution_time FLOAT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (team_id) REFERENCES teams (team_id) ON DELETE CASCADE,
                FOREIGN KEY (problem_id) REFERENCES problems (id) ON DELETE CASCADE
            )
        """)
        
        # Selection Log (Audit trail)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS selection_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id TEXT NOT NULL,
                player_id INTEGER NOT NULL,
                problem_id TEXT NOT NULL,
                status TEXT NOT NULL, -- 'success', 'conflict', 'rejected'
                reason TEXT,
                attempt_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (team_id) REFERENCES teams (team_id) ON DELETE CASCADE,
                FOREIGN KEY (player_id) REFERENCES players (id) ON DELETE CASCADE,
                FOREIGN KEY (problem_id) REFERENCES problems (id) ON DELETE CASCADE
            )
        """)
        
        # Test Cases table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS test_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                problem_id TEXT NOT NULL,
                input_data TEXT NOT NULL,
                expected_output TEXT NOT NULL,
                is_visible BOOLEAN DEFAULT 0,
                FOREIGN KEY (problem_id) REFERENCES problems (id) ON DELETE CASCADE
            )
        """)

        await db.commit()
