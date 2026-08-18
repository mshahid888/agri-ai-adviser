"""Consolidated Persistent Memory System for M14 Agricultural AI Agent.

Single source of truth for all persistence: farmers, memories, interactions,
sessions, context, and feedback.
"""
import sqlite3
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Any

logger = logging.getLogger(__name__)

DEFAULT_DB_DIR = Path(__file__).resolve().parent.parent / "data"


@dataclass
class FarmerProfile:
    farmer_id: str
    name: str = ""
    crop: str = ""
    country: str = ""
    province: str = ""
    district: str = ""
    farm_size: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class FarmerMemory:
    memory_id: str
    farmer_id: str
    memory_type: str
    content: str
    relevance_score: float = 0.0
    metadata_json: str = "{}"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Interaction:
    interaction_id: str
    farmer_id: str
    session_id: str
    query: str
    response: str
    intent: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Session:
    session_id: str
    farmer_id: str
    state_json: str = "{}"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_active: str = field(default_factory=lambda: datetime.now().isoformat())


class MemoryRepository:
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_db()

    def _init_db(self):
        cursor = self.conn.cursor()
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS farmers (
                farmer_id TEXT PRIMARY KEY,
                name TEXT DEFAULT '',
                crop TEXT DEFAULT '',
                country TEXT DEFAULT '',
                province TEXT DEFAULT '',
                district TEXT DEFAULT '',
                farm_size REAL DEFAULT 0.0,
                created_at TEXT,
                updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS memories (
                memory_id TEXT PRIMARY KEY,
                farmer_id TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                content TEXT NOT NULL,
                relevance_score REAL DEFAULT 0.0,
                metadata_json TEXT DEFAULT '{}',
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS interactions (
                interaction_id TEXT PRIMARY KEY,
                farmer_id TEXT NOT NULL,
                session_id TEXT DEFAULT '',
                query TEXT DEFAULT '',
                response TEXT DEFAULT '',
                intent TEXT DEFAULT '',
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                farmer_id TEXT DEFAULT '',
                state_json TEXT DEFAULT '{}',
                created_at TEXT,
                last_active TEXT
            );
            CREATE TABLE IF NOT EXISTS context (
                session_id TEXT PRIMARY KEY,
                data TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS feedback (
                interaction_id TEXT PRIMARY KEY,
                rating INTEGER,
                comment TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_memories_farmer ON memories(farmer_id, memory_type);
            CREATE INDEX IF NOT EXISTS idx_interactions_farmer ON interactions(farmer_id);
        """)
        self.conn.commit()
        logger.info("MemoryRepository initialized at %s", self.db_path)

    # ─── Farmer Profile ─────────────────────────────────────────────────

    def upsert_farmer(self, profile: FarmerProfile):
        with self.conn:
            self.conn.execute("""
                INSERT OR REPLACE INTO farmers
                (farmer_id, name, crop, country, province, district, farm_size, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                profile.farmer_id, profile.name, profile.crop, profile.country,
                profile.province, profile.district, profile.farm_size,
                profile.created_at, profile.updated_at,
            ))

    def get_farmer(self, farmer_id: str) -> Optional[FarmerProfile]:
        row = self.conn.execute(
            "SELECT * FROM farmers WHERE farmer_id = ?", (farmer_id,)
        ).fetchone()
        return FarmerProfile(**dict(row)) if row else None

    # ─── Memory ─────────────────────────────────────────────────────────

    def add_memory(self, memory: FarmerMemory):
        with self.conn:
            self.conn.execute("""
                INSERT OR REPLACE INTO memories
                (memory_id, farmer_id, memory_type, content, relevance_score, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                memory.memory_id, memory.farmer_id, memory.memory_type,
                memory.content, memory.relevance_score, memory.metadata_json,
                memory.created_at,
            ))

    def get_memories(
        self,
        farmer_id: str,
        memory_type: Optional[str] = None,
        limit: int = 10,
        min_relevance: float = 0.0,
    ) -> List[FarmerMemory]:
        query = "SELECT * FROM memories WHERE farmer_id = ? AND relevance_score >= ?"
        params: list[Any] = [farmer_id, min_relevance]
        if memory_type:
            query += " AND memory_type = ?"
            params.append(memory_type)
        query += " ORDER BY relevance_score DESC, created_at DESC LIMIT ?"
        params.append(limit)
        cursor = self.conn.execute(query, params)
        return [FarmerMemory(**dict(row)) for row in cursor.fetchall()]

    def search_memories(self, farmer_id: str, keywords: List[str], limit: int = 5) -> List[FarmerMemory]:
        if not keywords:
            return self.get_memories(farmer_id, limit=limit)
        conditions = " OR ".join(["content LIKE ?"] * len(keywords))
        params: list[Any] = [farmer_id] + [f"%{kw}%" for kw in keywords]
        query = f"SELECT * FROM memories WHERE farmer_id = ? AND ({conditions}) ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        cursor = self.conn.execute(query, params)
        return [FarmerMemory(**dict(row)) for row in cursor.fetchall()]

    # ─── Interactions ───────────────────────────────────────────────────

    def add_interaction(self, interaction: Interaction):
        with self.conn:
            self.conn.execute("""
                INSERT OR REPLACE INTO interactions
                (interaction_id, farmer_id, session_id, query, response, intent, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                interaction.interaction_id, interaction.farmer_id,
                interaction.session_id, interaction.query, interaction.response,
                interaction.intent, interaction.created_at,
            ))

    def get_interactions(self, farmer_id: str, limit: int = 5) -> List[Interaction]:
        cursor = self.conn.execute(
            "SELECT * FROM interactions WHERE farmer_id = ? ORDER BY created_at DESC LIMIT ?",
            (farmer_id, limit),
        )
        return [Interaction(**dict(row)) for row in cursor.fetchall()]

    # ─── Sessions ───────────────────────────────────────────────────────

    def upsert_session(self, session: Session):
        with self.conn:
            self.conn.execute("""
                INSERT OR REPLACE INTO sessions
                (session_id, farmer_id, state_json, created_at, last_active)
                VALUES (?, ?, ?, ?, ?)
            """, (
                session.session_id, session.farmer_id,
                session.state_json, session.created_at, session.last_active,
            ))

    def get_session(self, session_id: str) -> Optional[Session]:
        row = self.conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        return Session(**dict(row)) if row else None

    # ─── Context (lightweight key-value for session state) ──────────────

    def save_context(self, session_id: str, data: dict):
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO context (session_id, data) VALUES (?, ?)",
                (session_id, json.dumps(data)),
            )

    def get_context(self, session_id: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT data FROM context WHERE session_id = ?", (session_id,)
        ).fetchone()
        return json.loads(row[0]) if row else None

    # ─── Feedback ───────────────────────────────────────────────────────

    def save_feedback(self, interaction_id: str, rating: int, comment: str = ""):
        if not (1 <= rating <= 5):
            raise ValueError("Rating must be between 1 and 5.")
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO feedback (interaction_id, rating, comment) VALUES (?, ?, ?)",
                (interaction_id, rating, comment),
            )

    def get_feedback_stats(self) -> dict:
        row = self.conn.execute(
            "SELECT AVG(rating), COUNT(*) FROM feedback"
        ).fetchone()
        return {
            "average_rating": round(row[0] or 0.0, 2),
            "total_feedback": row[1] or 0,
        }

    def get_feedback(self, interaction_id: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM feedback WHERE interaction_id = ?", (interaction_id,)
        ).fetchone()
        return dict(row) if row else None

    def close(self):
        self.conn.close()
