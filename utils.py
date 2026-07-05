from textwrap import shorten

TITLE, DESCRIPTION, EDIT_TITLE, EDIT_DESC, EDIT_DATE = range(5)

PAGE_SIZE = 5

MOON = "🌙"
STAR = "✨"
BOOK = "📖"
MAG  = "🔍"
TRASH = "🗑"


def _esc(text: str) -> str:
    for char in ['\\', '_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']:
        text = text.replace(char, f'\\{char}')
    return text


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
