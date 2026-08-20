"""Chat persistence — SQLite CRUD for chats and messages.

Ref: https://docs.python.org/3/library/sqlite3.html
"""

import os
import sqlite3
from datetime import datetime


# --- Database path ---

DB_DIR = os.path.join(os.path.dirname(__file__), "data")
CHAT_DB_PATH = os.path.join(DB_DIR, "chat_history.db")


# --- Connection helper ---

def _connect() -> sqlite3.Connection:
    """Open a connection with row_factory for dict-like access.
    Ref: https://docs.python.org/3/library/sqlite3.html#sqlite3.Row
    """
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(CHAT_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


# --- Schema ---

def init_db():
    """Create tables if they don't exist.
    Ref: https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.executescript
    """
    conn = _connect()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS chats (
            id         TEXT PRIMARY KEY,
            title      TEXT NOT NULL DEFAULT 'New chat',
            agent      TEXT NOT NULL DEFAULT 'sql',
            model      TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS messages (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id    TEXT NOT NULL,
            role       TEXT NOT NULL,
            content    TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE
        );
    """)
    conn.commit()
    conn.close()


# --- Chat CRUD ---

def create_chat(chat_id: str, agent: str, model: str,
                title: str = "New chat") -> dict:
    """Insert a new chat and return it as a dict."""
    now = datetime.now().isoformat()
    conn = _connect()
    conn.execute(
        "INSERT INTO chats (id, title, agent, model, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (chat_id, title, agent, model, now),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM chats WHERE id = ?", (chat_id,)
    ).fetchone()
    conn.close()
    return dict(row)


def list_chats() -> list[dict]:
    """All chats, newest first."""
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM chats ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_chat(chat_id: str) -> dict | None:
    """Single chat by ID, or None."""
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM chats WHERE id = ?", (chat_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_chat(chat_id: str, **fields) -> dict | None:
    """Update allowed fields (title, agent, model) on a chat."""
    allowed = {"title", "agent", "model"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return get_chat(chat_id)

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [chat_id]

    conn = _connect()
    conn.execute(f"UPDATE chats SET {set_clause} WHERE id = ?", values)
    conn.commit()
    row = conn.execute(
        "SELECT * FROM chats WHERE id = ?", (chat_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_chat(chat_id: str) -> bool:
    """Delete a chat and cascade to its messages. Returns True if it existed."""
    conn = _connect()
    cur = conn.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0


# --- Message CRUD ---

def add_message(chat_id: str, role: str, content: str) -> dict:
    """Append a message to a chat."""
    now = datetime.now().isoformat()
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO messages (chat_id, role, content, created_at) "
        "VALUES (?, ?, ?, ?)",
        (chat_id, role, content, now),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM messages WHERE id = ?", (cur.lastrowid,)
    ).fetchone()
    conn.close()
    return dict(row)


def get_messages(chat_id: str) -> list[dict]:
    """All messages for a chat, oldest first."""
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM messages WHERE chat_id = ? ORDER BY created_at ASC",
        (chat_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
