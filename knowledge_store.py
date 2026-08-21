"""Wissensdatenbank - persistent knowledge base for agent learning.

Agents save useful findings (web search results, query patterns,
translations, code snippets) here. Future requests check the knowledge
base first, so the system gets smarter over time.
Ref: https://docs.python.org/3/library/sqlite3.html
"""

import os
import sqlite3
from datetime import datetime


# --- Database path ---

DB_DIR = os.path.join(os.path.dirname(__file__), "data")
KNOWLEDGE_DB_PATH = os.path.join(DB_DIR, "knowledge.db")


# --- Connection helper ---

def _connect() -> sqlite3.Connection:
    """Open a connection with row_factory for dict-like access."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(KNOWLEDGE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# --- Schema ---

def init_knowledge_db():
    """Create the knowledge table if it doesn't exist."""
    conn = _connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS knowledge (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            topic      TEXT NOT NULL,
            content    TEXT NOT NULL,
            source     TEXT NOT NULL DEFAULT 'agent',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


# --- CRUD ---

def save_entry(topic: str, content: str, source: str = "agent") -> dict:
    """Store a piece of knowledge. Returns the new entry."""
    now = datetime.now().isoformat()
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO knowledge (topic, content, source, created_at) "
        "VALUES (?, ?, ?, ?)",
        (topic, content, source, now),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM knowledge WHERE id = ?", (cur.lastrowid,)
    ).fetchone()
    conn.close()
    return dict(row)


def search_entries(query: str, limit: int = 10) -> list[dict]:
    """Search knowledge by keyword (matches topic and content).
    Ref: https://www.sqlite.org/lang_expr.html#the_like_glob_regexp_and_match_operators
    """
    conn = _connect()
    pattern = f"%{query}%"
    rows = conn.execute(
        "SELECT * FROM knowledge "
        "WHERE topic LIKE ? OR content LIKE ? "
        "ORDER BY created_at DESC LIMIT ?",
        (pattern, pattern, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_entries(limit: int = 50) -> list[dict]:
    """Most recent knowledge entries."""
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM knowledge ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_entry(entry_id: int) -> dict | None:
    """Single entry by ID."""
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM knowledge WHERE id = ?", (entry_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_entry(entry_id: int) -> bool:
    """Delete a knowledge entry. Returns True if it existed."""
    conn = _connect()
    cur = conn.execute("DELETE FROM knowledge WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0
