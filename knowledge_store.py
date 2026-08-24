"""Wissensdatenbank - persistent knowledge base for agent learning.

Agents save useful findings (web search results, query patterns,
translations, code snippets) here. Future requests check the knowledge
base first, so the system gets smarter over time.

Uses SQLite FTS5 for fast full-text search.
Ref: https://docs.python.org/3/library/sqlite3.html
Ref: https://www.sqlite.org/fts5.html
"""

import os
import sqlite3
from datetime import datetime
from config import KNOWLEDGE_DB_PATH, DATA_DIR


# --- Connection helper ---

def _connect() -> sqlite3.Connection:
    """Open a connection with row_factory for dict-like access."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(KNOWLEDGE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# --- Schema ---

def init_knowledge_db():
    """Create the knowledge table and FTS5 index if they don't exist.

    The FTS5 virtual table mirrors topic + content for fast full-text search.
    Triggers keep the two tables in sync automatically.
    Ref: https://www.sqlite.org/fts5.html
    """
    conn = _connect()

    # -- Main table --
    conn.execute("""
        CREATE TABLE IF NOT EXISTS knowledge (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            topic      TEXT NOT NULL,
            content    TEXT NOT NULL,
            source     TEXT NOT NULL DEFAULT 'agent',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # -- FTS5 virtual table for full-text search --
    try:
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
                topic, content,
                content=knowledge,
                content_rowid=id
            )
        """)

        # -- Sync triggers --
        conn.executescript("""
            CREATE TRIGGER IF NOT EXISTS knowledge_ai AFTER INSERT ON knowledge BEGIN
                INSERT INTO knowledge_fts(rowid, topic, content)
                VALUES (new.id, new.topic, new.content);
            END;

            CREATE TRIGGER IF NOT EXISTS knowledge_ad AFTER DELETE ON knowledge BEGIN
                INSERT INTO knowledge_fts(knowledge_fts, rowid, topic, content)
                VALUES ('delete', old.id, old.topic, old.content);
            END;

            CREATE TRIGGER IF NOT EXISTS knowledge_au AFTER UPDATE ON knowledge BEGIN
                INSERT INTO knowledge_fts(knowledge_fts, rowid, topic, content)
                VALUES ('delete', old.id, old.topic, old.content);
                INSERT INTO knowledge_fts(rowid, topic, content)
                VALUES (new.id, new.topic, new.content);
            END;
        """)

        # -- Rebuild FTS index from existing data --
        conn.execute("INSERT INTO knowledge_fts(knowledge_fts) VALUES('rebuild')")
    except Exception:
        # FTS5 might not be available on all SQLite builds
        pass

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


def save_entry_dedup(topic: str, content: str, source: str = "agent") -> dict:
    """Save knowledge, but update if a similar topic already exists.

    Checks for exact topic match first. If found, updates the content
    and source instead of creating a duplicate.
    """
    conn = _connect()
    existing = conn.execute(
        "SELECT id FROM knowledge WHERE topic = ?", (topic,)
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE knowledge SET content = ?, source = ?, created_at = ? WHERE id = ?",
            (content, source, datetime.now().isoformat(), existing["id"]),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM knowledge WHERE id = ?", (existing["id"],)
        ).fetchone()
    else:
        now = datetime.now().isoformat()
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
    """Search knowledge by keyword. Uses FTS5 when available, falls back to LIKE.

    Ref: https://www.sqlite.org/fts5.html
    """
    conn = _connect()

    # -- Try FTS5 first (much faster and smarter matching) --
    try:
        # FTS5 query: escape special chars, add prefix matching
        fts_query = query.replace('"', '""')
        rows = conn.execute(
            """SELECT k.* FROM knowledge k
               JOIN knowledge_fts f ON k.id = f.rowid
               WHERE knowledge_fts MATCH ?
               ORDER BY rank
               LIMIT ?""",
            (f'"{fts_query}"', limit),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        pass

    # -- Fallback to LIKE search --
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


def count_entries() -> int:
    """Total number of knowledge entries."""
    conn = _connect()
    count = conn.execute("SELECT COUNT(*) FROM knowledge").fetchone()[0]
    conn.close()
    return count
