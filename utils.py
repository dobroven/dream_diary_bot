from datetime import datetime
from textwrap import shorten

MIN_DREAMS_FOR_MAP = 10
MIN_NEW_DREAMS_FOR_MAP = 7
MAP_REFRESH_DAYS = 14
MODEL_LABEL = "🧠 Nemotron 3.5 Super VL"

TITLE, DESCRIPTION, EDIT_TITLE, EDIT_DESC, EDIT_DATE = range(5)

PAGE_SIZE = 5

MOON = "🌙"
STAR = "✨"
BOOK = "📖"
MAG  = "🔍"
TRASH = "🗑"
VOICE = "🎤"


def _esc(text: str) -> str:
    for char in ['\\', '_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']:
        text = text.replace(char, f'\\{char}')
    return text


def format_date(value: str) -> str:
    """YYYY-MM-DD (или ISO datetime) -> DD.MM.YYYY."""
    if not value:
        return ""
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return value


def dream_card(row, index: int | None = None, list_mode: bool = False, snippet_width: int = 80) -> str:
    if list_mode:
        snippet = _esc(shorten(row["description"], snippet_width, placeholder="…"))
        return (
            f"\\#{index} {MOON} *{_esc(row['title'])}* — {_esc(row['date'])}\n"
            f"    {snippet}"
        )
    prefix = f"*{index}.* " if index is not None else ""
    return (
        f"{prefix}{MOON} *{_esc(row['title'])}*\n"
        f"📅 {_esc(row['date'])}\n"
        f"{_esc(row['description'])}"
    )
