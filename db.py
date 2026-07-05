import logging
import sqlite3
from datetime import date
from pathlib import Path
from typing import Optional

DB_PATH = str(Path(__file__).parent / "dreams.db")

log = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS dreams (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                date        TEXT    NOT NULL,
                title       TEXT    NOT NULL,
                description TEXT    NOT NULL,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_dreams_user_date
            ON dreams (user_id, date DESC)
        """)
        conn.commit()


# ── CRUD ──────────────────────────────────────────────────────────────────────

def add_dream(
    user_id: int,
    title: str,
    description: str,
    dream_date: Optional[str] = None,
) -> int | None:
    """Insert a dream and return its new id, or None on error."""
    dream_date = dream_date or date.today().isoformat()
    try:
        with get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO dreams (user_id, date, title, description) VALUES (?, ?, ?, ?)",
                (user_id, dream_date, title, description),
            )
            conn.commit()
            return cur.lastrowid
    except sqlite3.Error as e:
        log.exception("Ошибка при добавлении сна: %s", e)
        return None


def list_dreams(user_id: int, limit: int = 10, offset: int = 0) -> list[sqlite3.Row]:
    """Return the most recent dreams for a user (paginated)."""
    try:
        with get_connection() as conn:
            return conn.execute(
                """
                SELECT id, date, title, description
                FROM dreams
                WHERE user_id = ?
                ORDER BY date DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (user_id, limit, offset),
            ).fetchall()
    except sqlite3.Error as e:
        log.exception("Ошибка при загрузке списка снов: %s", e)
        return []


def count_dreams(user_id: int) -> int:
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM dreams WHERE user_id = ?", (user_id,)
            ).fetchone()
            return row[0]
    except sqlite3.Error as e:
        log.exception("Ошибка при подсчёте снов: %s", e)
        return 0


def list_all_dreams(user_id: int) -> list[sqlite3.Row]:
    """Return ALL dreams for a user (no pagination)."""
    try:
        with get_connection() as conn:
            return conn.execute(
                """
                SELECT id, date, title, description
                FROM dreams
                WHERE user_id = ?
                ORDER BY date DESC, id DESC
                """,
                (user_id,),
            ).fetchall()
    except sqlite3.Error as e:
        log.exception("Ошибка при загрузке всех снов: %s", e)
        return []


def search_dreams(user_id: int, query: str) -> list[sqlite3.Row]:
    """Case-insensitive search across title + description.

    SQLite's built-in LIKE is case-sensitive for non-ASCII (Cyrillic, etc.),
    so we fetch rows and filter in Python using str.casefold().
    """
    query_lower = query.casefold()
    MAX_PREFETCH = 1000
    try:
        with get_connection() as conn:
            all_rows = conn.execute(
                """
                SELECT id, date, title, description
                FROM dreams
                WHERE user_id = ?
                ORDER BY date DESC, id DESC
                LIMIT ?
                """,
                (user_id, MAX_PREFETCH),
            ).fetchall()
    except sqlite3.Error as e:
        log.exception("Ошибка при поиске снов: %s", e)
        return []

    return [
        row for row in all_rows
        if query_lower in row["title"].casefold()
        or query_lower in row["description"].casefold()
    ][:20]


def get_dream(user_id: int, dream_id: int) -> sqlite3.Row | None:
    """Return a dream row by its ID for the given user."""
    try:
        with get_connection() as conn:
            return conn.execute(
                "SELECT id, date, title, description FROM dreams WHERE user_id = ? AND id = ?",
                (user_id, dream_id),
            ).fetchone()
    except sqlite3.Error as e:
        log.exception("Ошибка при получении сна: %s", e)
        return None

def get_dream_by_title(user_id: int, title: str) -> sqlite3.Row | None:
    """Return a dream row matching the exact title (case‑insensitive) for a user.

    Uses Python casefold for correct Cyrillic handling.
    """
    title_key = title.casefold()
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, date, title, description
                FROM dreams
                WHERE user_id = ?
                ORDER BY date DESC, id DESC
                LIMIT 1000
                """,
                (user_id,),
            ).fetchall()
    except sqlite3.Error as e:
        log.exception("Ошибка при получении сна по заголовку: %s", e)
        return None

    for row in rows:
        if row["title"].casefold() == title_key:
            return row
    return None


def delete_dream_by_title(user_id: int, title: str) -> bool:
    """Delete a dream by title (case‑insensitive) for the given user.

    Uses Python casefold for correct Cyrillic handling.
    """
    title_key = title.casefold()
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, title
                FROM dreams
                WHERE user_id = ?
                ORDER BY date DESC, id DESC
                LIMIT 1000
                """,
                (user_id,),
            ).fetchall()
            for row in rows:
                if row["title"].casefold() == title_key:
                    cur = conn.execute(
                        "DELETE FROM dreams WHERE user_id = ? AND id = ?",
                        (user_id, row["id"]),
                    )
                    conn.commit()
                    return cur.rowcount > 0
    except sqlite3.Error as e:
        log.exception("Ошибка при удалении сна по заголовку: %s", e)
        return False
    return False

def count_dreams_by_title(user_id: int, title: str) -> int:
    """Count dreams whose title matches (case‑insensitive)."""
    title_key = title.casefold()
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT title
                FROM dreams
                WHERE user_id = ?
                ORDER BY date DESC, id DESC
                LIMIT 1000
                """,
                (user_id,),
            ).fetchall()
    except sqlite3.Error as e:
        log.exception("Ошибка при подсчёте снов по заголовку: %s", e)
        return 0
    return sum(1 for row in rows if row["title"].casefold() == title_key)


def delete_dream(user_id: int, dream_id: int) -> bool:
    """Delete a dream by its ID for the given user."""
    try:
        with get_connection() as conn:
            cur = conn.execute(
                "DELETE FROM dreams WHERE user_id = ? AND id = ?",
                (user_id, dream_id),
            )
            conn.commit()
            return cur.rowcount > 0
    except sqlite3.Error as e:
        log.exception("Ошибка при удалении сна: %s", e)
        return False


