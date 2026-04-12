"""Short-term memory — SQLite-based recent operations log."""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "memory.db"


class ShortTermMemory:
    """Store and retrieve recent operations (rolling 7-day window)."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS operations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    user_input TEXT NOT NULL,
                    skill_used TEXT NOT NULL,
                    intent TEXT,
                    commands_run TEXT,
                    analysis TEXT,
                    react_steps INTEGER DEFAULT 0
                )
            """)
            conn.commit()

    def save(self, user_input: str, skill: str, intent: str,
             commands: list[dict], analysis: str, react_steps: int = 0):
        """Save an operation record."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO operations 
                   (timestamp, user_input, skill_used, intent, commands_run, analysis, react_steps)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    datetime.now().isoformat(),
                    user_input,
                    skill,
                    intent,
                    json.dumps(commands, ensure_ascii=False),
                    analysis,
                    react_steps,
                ),
            )
            conn.commit()

    def get_recent(self, skill: str = None, limit: int = 5) -> list[dict]:
        """Retrieve recent operations, optionally filtered by skill."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if skill:
                rows = conn.execute(
                    "SELECT * FROM operations WHERE skill_used = ? ORDER BY timestamp DESC LIMIT ?",
                    (skill, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM operations ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]

    def cleanup(self, days: int = 7):
        """Remove records older than N days."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM operations WHERE timestamp < ?", (cutoff,))
            conn.commit()