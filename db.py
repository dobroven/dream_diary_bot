import json
import logging
import sqlite3
from datetime import date, datetime, timedelta
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS dream_maps (
                user_id       INTEGER PRIMARY KEY,
                patterns_json TEXT    NOT NULL,
                dreams_count  INTEGER NOT NULL,
                period_start  TEXT    NOT NULL,
                period_end    TEXT    NOT NULL,
                generated_at  TEXT    NOT NULL
            )
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


def list_dreams_for_map(
    user_id: int,
    days: int = 14,
    min_count: int = 14,
    today: date | None = None,
) -> list[sqlite3.Row]:
    """Сны для карты: последние `days` календарных дней, включая сегодня.

    Если в окне меньше `min_count` снов, добираем более ранние, пока
    не наберём минимум. Если всего снов меньше — возвращаем всё.
    """
    today = today or date.today()
    cutoff = (today - timedelta(days=days - 1)).isoformat()
    today_str = today.isoformat()

    try:
        with get_connection() as conn:
            recent = conn.execute(
                """
                SELECT id, date, title, description
                FROM dreams
                WHERE user_id = ? AND date >= ? AND date <= ?
                ORDER BY date DESC, id DESC
                """,
                (user_id, cutoff, today_str),
            ).fetchall()

            if len(recent) >= min_count:
                return recent

            need = min_count - len(recent)
            earlier = conn.execute(
                """
                SELECT id, date, title, description
                FROM dreams
                WHERE user_id = ? AND date < ?
                ORDER BY date DESC, id DESC
                LIMIT ?
                """,
                (user_id, cutoff, need),
            ).fetchall()

            return recent + earlier
    except sqlite3.Error as e:
        log.exception("Ошибка при загрузке снов для карты: %s", e)
        return []


def save_dream_map(
    user_id: int,
    patterns: list[dict],
    dreams_count: int,
    period_start: str,
    period_end: str,
    generated_at: str | None = None,
) -> bool:
    """Сохраняет последнюю карту снов пользователя."""
    generated_at = generated_at or datetime.now().isoformat(timespec="seconds")
    patterns_json = json.dumps(patterns, ensure_ascii=False)
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO dream_maps (
                    user_id, patterns_json, dreams_count,
                    period_start, period_end, generated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    patterns_json = excluded.patterns_json,
                    dreams_count  = excluded.dreams_count,
                    period_start  = excluded.period_start,
                    period_end    = excluded.period_end,
                    generated_at  = excluded.generated_at
                """,
                (
                    user_id,
                    patterns_json,
                    dreams_count,
                    period_start,
                    period_end,
                    generated_at,
                ),
            )
            conn.commit()
            return True
    except sqlite3.Error as e:
        log.exception("Ошибка при сохранении карты снов: %s", e)
        return False


def get_dream_map(user_id: int) -> sqlite3.Row | None:
    try:
        with get_connection() as conn:
            return conn.execute(
                """
                SELECT user_id, patterns_json, dreams_count,
                       period_start, period_end, generated_at
                FROM dream_maps
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
    except sqlite3.Error as e:
        log.exception("Ошибка при загрузке карты снов: %s", e)
        return None


def list_users_due_for_map(
    interval_days: int = 14,
    min_dreams: int = 10,
    now: datetime | None = None,
) -> list[int]:
    """Пользователи, которым пора обновить карту."""
    now = now or datetime.now()
    cutoff = (now - timedelta(days=interval_days)).isoformat(timespec="seconds")
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT d.user_id
                FROM (
                    SELECT user_id, COUNT(*) AS total
                    FROM dreams
                    GROUP BY user_id
                ) AS d
                LEFT JOIN dream_maps AS m ON m.user_id = d.user_id
                WHERE d.total >= ?
                  AND (m.generated_at IS NULL OR m.generated_at <= ?)
                ORDER BY d.user_id
                """,
                (min_dreams, cutoff),
            ).fetchall()
            return [row["user_id"] for row in rows]
    except sqlite3.Error as e:
        log.exception("Ошибка при поиске пользователей для карты: %s", e)
        return []


def _fetch_user_dreams(user_id: int, limit: int = 1000) -> list[sqlite3.Row]:
    try:
        with get_connection() as conn:
            return conn.execute(
                "SELECT id, date, title, description FROM dreams"
                " WHERE user_id = ? ORDER BY date DESC, id DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
    except sqlite3.Error as e:
        log.exception("Ошибка при загрузке снов пользователя %d: %s", user_id, e)
        return []


def search_dreams(user_id: int, query: str) -> list[sqlite3.Row]:
    """Case-insensitive search across title + description.

    SQLite's built-in LIKE is case-sensitive for non-ASCII (Cyrillic, etc.),
    so we fetch rows and filter in Python using str.casefold().
    """
    query_lower = query.casefold()
    return [
        row for row in _fetch_user_dreams(user_id)
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
    for row in _fetch_user_dreams(user_id):
        if row["title"].casefold() == title_key:
            return row
    return None


def delete_dream_by_title(user_id: int, title: str) -> bool:
    """Delete a dream by title (case‑insensitive) for the given user.

    Uses Python casefold for correct Cyrillic handling.
    """
    title_key = title.casefold()
    for row in _fetch_user_dreams(user_id):
        if row["title"].casefold() == title_key:
            with get_connection() as conn:
                cur = conn.execute(
                    "DELETE FROM dreams WHERE user_id = ? AND id = ?",
                    (user_id, row["id"]),
                )
                conn.commit()
                return cur.rowcount > 0
    return False


def count_dreams_by_title(user_id: int, title: str) -> int:
    """Count dreams whose title matches (case‑insensitive)."""
    title_key = title.casefold()
    return sum(
        1 for row in _fetch_user_dreams(user_id)
        if row["title"].casefold() == title_key
    )


def update_dream(user_id: int, dream_id: int, title: str, description: str, dream_date: str) -> bool:
    """Update title, description and date of a dream. Returns True on success."""
    try:
        with get_connection() as conn:
            cur = conn.execute(
                """
                UPDATE dreams
                SET title = ?, description = ?, date = ?
                WHERE user_id = ? AND id = ?
                """,
                (title, description, dream_date, user_id, dream_id),
            )
            conn.commit()
            return cur.rowcount > 0
    except sqlite3.Error as e:
        log.exception("Ошибка при обновлении сна: %s", e)
        return False


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


