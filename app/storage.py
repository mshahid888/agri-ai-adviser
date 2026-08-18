"""SQLite-based storage for the Agricultural AI Agent.

Handles persistent storage for farmer contexts, memories, and feedback.
"""
import sqlite3
import json
from pathlib import Path
from typing import Optional, Any

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "agent.db"

def init_db():
    """Initialize the SQLite database schema."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS farmer_context (
            session_id TEXT PRIMARY KEY,
            data TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            interaction_id TEXT,
            rating INTEGER,
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def save_context(session_id: str, data: dict):
    """Save farmer context to SQLite."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "REPLACE INTO farmer_context (session_id, data) VALUES (?, ?)",
        (session_id, json.dumps(data)),
    )
    conn.commit()
    conn.close()

def get_context(session_id: str) -> Optional[dict]:
    """Retrieve farmer context from SQLite."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT data FROM farmer_context WHERE session_id = ?", (session_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return None

def save_feedback(interaction_id: str, rating: int, comment: str):
    """Save farmer feedback."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO feedback (interaction_id, rating, comment) VALUES (?, ?, ?)",
        (interaction_id, rating, comment),
    )
    conn.commit()
    conn.close()
