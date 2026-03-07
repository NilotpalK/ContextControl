import sqlite3
import uuid
from typing import Optional
from config import SQLITE_PATH


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create all tables if they don't exist. Called once on startup."""
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id             TEXT PRIMARY KEY,
                user_id        TEXT NOT NULL,
                title          TEXT,
                created_at     TEXT DEFAULT (datetime('now')),
                last_active    TEXT DEFAULT (datetime('now')),
                exchange_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS exchanges (
                id          TEXT PRIMARY KEY,
                session_id  TEXT NOT NULL,
                user_id     TEXT NOT NULL,
                user_turn   TEXT NOT NULL,
                asst_turn   TEXT NOT NULL,
                hidden      INTEGER DEFAULT 0,
                created_at  TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );

            CREATE TABLE IF NOT EXISTS topics (
                name           TEXT NOT NULL,
                session_id     TEXT NOT NULL,
                user_id        TEXT NOT NULL,
                parent         TEXT,
                status         TEXT DEFAULT 'active',
                exchange_count INTEGER DEFAULT 0,
                PRIMARY KEY (name, session_id)
            );

            CREATE TABLE IF NOT EXISTS exchange_topics (
                exchange_id      TEXT NOT NULL,
                topic_name       TEXT NOT NULL,
                is_primary       INTEGER NOT NULL,
                is_mention_only  INTEGER NOT NULL,
                FOREIGN KEY (exchange_id) REFERENCES exchanges(id)
            );

            CREATE TABLE IF NOT EXISTS exchange_refs (
                from_exchange_id  TEXT NOT NULL,
                to_exchange_id    TEXT NOT NULL,
                reference_type    TEXT NOT NULL,
                FOREIGN KEY (from_exchange_id) REFERENCES exchanges(id),
                FOREIGN KEY (to_exchange_id)   REFERENCES exchanges(id)
            );

            CREATE TABLE IF NOT EXISTS session_imports (
                id                TEXT PRIMARY KEY,
                target_session_id TEXT NOT NULL,
                source_session_id TEXT NOT NULL,
                import_type       TEXT NOT NULL,
                imported_at       TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (target_session_id) REFERENCES sessions(id),
                FOREIGN KEY (source_session_id) REFERENCES sessions(id)
            );

            CREATE INDEX IF NOT EXISTS idx_exchanges_session
                ON exchanges(session_id);
            CREATE INDEX IF NOT EXISTS idx_exchange_topics_exchange
                ON exchange_topics(exchange_id);
            CREATE INDEX IF NOT EXISTS idx_exchange_topics_topic
                ON exchange_topics(topic_name);
            CREATE INDEX IF NOT EXISTS idx_topics_session
                ON topics(session_id);
        """)


# ── Sessions ───────────────────────────────────────────────────────────────────

def create_session(user_id: str, title: Optional[str] = None) -> str:
    session_id = f"session_{uuid.uuid4().hex[:8]}"
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO sessions (id, user_id, title) VALUES (?, ?, ?)",
            (session_id, user_id, title)
        )
    return session_id


def get_session(session_id: str) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM sessions WHERE id = ?",
            (session_id,)
        ).fetchone()


def get_user_sessions(user_id: str) -> list:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM sessions WHERE user_id = ? ORDER BY last_active DESC",
            (user_id,)
        ).fetchall()


def delete_session(session_id: str):
    """Delete a session entirely, securely cascading down to all relevant tables."""
    with get_conn() as conn:
        # Delete related exchange refs
        conn.execute(
            "DELETE FROM exchange_refs WHERE from_exchange_id IN (SELECT id FROM exchanges WHERE session_id = ?)",
            (session_id,)
        )
        conn.execute(
            "DELETE FROM exchange_refs WHERE to_exchange_id IN (SELECT id FROM exchanges WHERE session_id = ?)",
            (session_id,)
        )
        # Delete related exchange tags
        conn.execute(
            "DELETE FROM exchange_topics WHERE exchange_id IN (SELECT id FROM exchanges WHERE session_id = ?)",
            (session_id,)
        )
        # Delete exchanges
        conn.execute("DELETE FROM exchanges WHERE session_id = ?", (session_id,))
        # Delete imports
        conn.execute("DELETE FROM session_imports WHERE target_session_id = ? OR source_session_id = ?", (session_id, session_id))
        # Delete topics
        conn.execute("DELETE FROM topics WHERE session_id = ?", (session_id,))
        # Finally delete session
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))


def update_session_title(session_id: str, title: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE sessions SET title = ? WHERE id = ?",
            (title, session_id)
        )


def touch_session(session_id: str):
    """Update last_active timestamp."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE sessions SET last_active = datetime('now') WHERE id = ?",
            (session_id,)
        )


# ── Exchanges ──────────────────────────────────────────────────────────────────

def save_exchange(session_id: str, user_id: str, user_turn: str, asst_turn: str) -> str:
    exchange_id = f"exchange_{uuid.uuid4().hex[:8]}"
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO exchanges (id, session_id, user_id, user_turn, asst_turn)
               VALUES (?, ?, ?, ?, ?)""",
            (exchange_id, session_id, user_id, user_turn, asst_turn)
        )
        conn.execute(
            "UPDATE sessions SET exchange_count = exchange_count + 1, last_active = datetime('now') WHERE id = ?",
            (session_id,)
        )
    return exchange_id


def get_exchange(exchange_id: str) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM exchanges WHERE id = ?",
            (exchange_id,)
        ).fetchone()


def get_session_exchanges(session_id: str, include_hidden: bool = False) -> list:
    """Get all exchanges for a session ordered chronologically."""
    with get_conn() as conn:
        if include_hidden:
            return conn.execute(
                "SELECT * FROM exchanges WHERE session_id = ? ORDER BY created_at ASC",
                (session_id,)
            ).fetchall()
        return conn.execute(
            "SELECT * FROM exchanges WHERE session_id = ? AND hidden = 0 ORDER BY created_at ASC",
            (session_id,)
        ).fetchall()


def hide_exchange(exchange_id: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE exchanges SET hidden = 1 WHERE id = ?",
            (exchange_id,)
        )


def show_exchange(exchange_id: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE exchanges SET hidden = 0 WHERE id = ?",
            (exchange_id,)
        )


def get_last_exchange(session_id: str) -> Optional[sqlite3.Row]:
    """Get the most recent exchange in a session. Used as fallback by tagger."""
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM exchanges WHERE session_id = ? ORDER BY created_at DESC LIMIT 1",
            (session_id,)
        ).fetchone()


# ── Topics ─────────────────────────────────────────────────────────────────────

def upsert_topic(name: str, session_id: str, user_id: str, parent: Optional[str] = None):
    """Create topic if it doesn't exist, otherwise increment exchange_count."""
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT * FROM topics WHERE name = ? AND session_id = ?",
            (name, session_id)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE topics SET exchange_count = exchange_count + 1 WHERE name = ? AND session_id = ?",
                (name, session_id)
            )
        else:
            conn.execute(
                """INSERT INTO topics (name, session_id, user_id, parent, status, exchange_count)
                   VALUES (?, ?, ?, ?, 'active', 1)""",
                (name, session_id, user_id, parent)
            )


def get_topics(session_id: str) -> list:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM topics WHERE session_id = ? ORDER BY exchange_count DESC",
            (session_id,)
        ).fetchall()


def get_topic_names(session_id: str) -> list[str]:
    """Return just topic names for a session. Used by tagger to build context."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT name FROM topics WHERE session_id = ?",
            (session_id,)
        ).fetchall()
        return [r["name"] for r in rows]


def set_topic_status(name: str, session_id: str, status: str) -> int:
    """
    Flip all topics whose name OR parent contains 'name' (case-insensitive).
    Returns the number of rows updated.
    Supports prefix/substring matching so 'Postgres' matches
    'Postgres Setup', 'Postgres Indexing', and topics with parent='Postgres'.
    """
    with get_conn() as conn:
        cur = conn.execute(
            """UPDATE topics SET status = ?
               WHERE session_id = ?
               AND (instr(lower(name), lower(?)) > 0
                 OR instr(lower(coalesce(parent,'')), lower(?)) > 0)""",
            (status, session_id, name, name)
        )
        return cur.rowcount


def get_matched_topic_names(name: str, session_id: str) -> list[str]:
    """Return all exact topic names whose name OR parent contains `name` (case-insensitive)."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT name FROM topics
               WHERE session_id = ?
               AND (instr(lower(name), lower(?)) > 0
                 OR instr(lower(coalesce(parent,'')), lower(?)) > 0)""",
            (session_id, name, name)
        ).fetchall()
        return [r["name"] for r in rows]


def get_hidden_topics(session_id: str) -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT name FROM topics WHERE session_id = ? AND status = 'hidden'",
            (session_id,)
        ).fetchall()
        return [r["name"] for r in rows]


def get_active_topics(session_id: str) -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT name FROM topics WHERE session_id = ? AND status = 'active'",
            (session_id,)
        ).fetchall()
        return [r["name"] for r in rows]


# ── Exchange topics ────────────────────────────────────────────────────────────

def save_exchange_tag(
    exchange_id: str,
    topic_name: str,
    is_primary: bool,
    is_mention_only: bool
):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO exchange_topics
               (exchange_id, topic_name, is_primary, is_mention_only)
               VALUES (?, ?, ?, ?)""",
            (exchange_id, topic_name, int(is_primary), int(is_mention_only))
        )


def get_exchanges_for_topic(topic_name: str, session_id: str) -> list:
    """All exchanges tagged with this topic for this session."""
    with get_conn() as conn:
        return conn.execute(
            """SELECT e.* FROM exchanges e
               JOIN exchange_topics et ON e.id = et.exchange_id
               WHERE et.topic_name = ? AND e.session_id = ?
               ORDER BY e.created_at ASC""",
            (topic_name, session_id)
        ).fetchall()


def get_topics_for_exchange(exchange_id: str) -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT topic_name FROM exchange_topics WHERE exchange_id = ?",
            (exchange_id,)
        ).fetchall()
        return [r["topic_name"] for r in rows]


def get_primary_topics_for_exchange(exchange_id: str) -> list[str]:
    """Return only the primary (non-mention-only) topic links for an exchange.
    Used by cascade logic to decide hide eligibility — bare mention tags
    like 'Postgres' or 'index' shouldn't prevent an exchange from being hidden.
    """
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT topic_name FROM exchange_topics WHERE exchange_id = ? AND is_mention_only = 0",
            (exchange_id,)
        ).fetchall()
        return [r["topic_name"] for r in rows]


# ── Exchange refs ──────────────────────────────────────────────────────────────

def save_exchange_ref(from_id: str, to_id: str, ref_type: str):
    """Store a directional chain reference edge."""
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO exchange_refs
               (from_exchange_id, to_exchange_id, reference_type)
               VALUES (?, ?, ?)""",
            (from_id, to_id, ref_type)
        )


def get_exchanges_referencing(exchange_id: str) -> list[str]:
    """Find all exchanges that point TO this exchange. Used for cascade."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT from_exchange_id FROM exchange_refs WHERE to_exchange_id = ?",
            (exchange_id,)
        ).fetchall()
        return [r["from_exchange_id"] for r in rows]


def get_reference_target(exchange_id: str) -> Optional[str]:
    """Return what exchange this one references, if any."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT to_exchange_id FROM exchange_refs WHERE from_exchange_id = ?",
            (exchange_id,)
        ).fetchone()
        return row["to_exchange_id"] if row else None


# ── Session imports ────────────────────────────────────────────────────────────

def save_session_import(target_session_id: str, source_session_id: str, import_type: str):
    import_id = f"import_{uuid.uuid4().hex[:8]}"
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO session_imports
               (id, target_session_id, source_session_id, import_type)
               VALUES (?, ?, ?, ?)""",
            (import_id, target_session_id, source_session_id, import_type)
        )
    return import_id


def get_imports_for_session(session_id: str) -> list:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM session_imports WHERE target_session_id = ?",
            (session_id,)
        ).fetchall()


def delete_session_import(target_session_id: str, source_session_id: str):
    with get_conn() as conn:
        conn.execute(
            """DELETE FROM session_imports
               WHERE target_session_id = ? AND source_session_id = ?""",
            (target_session_id, source_session_id)
        )