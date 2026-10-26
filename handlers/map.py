import json
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import db
from utils import BOOK, MIN_DREAMS_FOR_MAP, MODEL_LABEL, _esc, format_date

log = logging.getLogger(__name__)

MAIN_MENU = InlineKeyboardMarkup(
    [[InlineKeyboardButton("🏠 Главная", callback_data="menu:main")]]
)


def _split_text(text: str, limit: int = 4096) -> list[str]:
    """Делит длинный текст на части, не разрывая строки без необходимости."""
    parts = []
    while len(text) > limit:
        idx = text.rfind("\n", 0, limit)
        if idx <= 0:
            idx = text.rfind(" ", 0, limit)
        if idx <= 0:
            idx = limit
        parts.append(text[:idx])
        text = text[idx:].lstrip("\n ")
    parts.append(text)
    return parts


async def _replace(update: Update, text: str, markup=None) -> None:
    """Заменяет сообщение меню (callback) или отправляет новое (команда)."""
    kwargs = {"text": text, "parse_mode": ParseMode.MARKDOWN_V2}
    if markup is not None:
        kwargs["reply_markup"] = markup

    if update.callback_query:
        await update.callback_query.edit_message_text(**kwargs)
    else:
        await update.message.reply_text(**kwargs)


async def _follow(update: Update, text: str, markup=None) -> None:
    kwargs = {"text": text, "parse_mode": ParseMode.MARKDOWN_V2}
    if markup is not None:
        kwargs["reply_markup"] = markup

    if update.callback_query:
        await update.callback_query.message.reply_text(**kwargs)
    else:
        await update.message.reply_text(**kwargs)


async def _send_result(update: Update, text: str) -> None:
    parts = _split_text(text)
    for i, part in enumerate(parts):
        markup = MAIN_MENU if i == len(parts) - 1 else None
        if i == 0:
            await _replace(update, part, markup)
        else:
            await _follow(update, part, markup)


def _cached_patterns(raw: str) -> list[dict]:
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("patterns_json is not a list")
    return [item for item in data if isinstance(item, dict)]


async def cmd_map(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    total = db.count_dreams(user_id)
    cached = db.get_dream_map(user_id)

    if cached is None:
        if total < MIN_DREAMS_FOR_MAP:
            text = (
                f"{BOOK} Для карты нужно минимум {MIN_DREAMS_FOR_MAP} снов. "
                f"Сейчас: {total}."
            )
        else:
            text = (
                "🗺 Карта ещё не составлена. "
                "Она появится после ближайшего автоматического обновления."
            )
        await _replace(update, _esc(text), MAIN_MENU)
        return

    try:
        patterns = _cached_patterns(cached["patterns_json"])
    except (TypeError, ValueError) as e:
        log.exception("Не удалось прочитать сохранённую карту снов: %s", e)
        await _replace(
            update,
            _esc("❌ Не удалось прочитать сохранённую карту. Попробуй позже."),
            MAIN_MENU,
        )
        return

    updated = format_date(str(cached["generated_at"]))
    period_start = format_date(str(cached["period_start"]))
    period_end = format_date(str(cached["period_end"]))
    period = f"{period_start} — {period_end}" if period_start and period_end else "—"

    lines = [
        f"🗺 *Карта сновидений* \\({_esc(MODEL_LABEL)}\\)",
        f"Обновлено: {_esc(updated)}",
        f"Сны за период: {_esc(period)}",
        f"Всего снов: {total} · в анализ вошло: {cached['dreams_count']}",
    ]
    if total < MIN_DREAMS_FOR_MAP:
        lines.append(
            _esc(
                f"Сейчас снов: {total}. "
                f"Для новой карты нужно минимум {MIN_DREAMS_FOR_MAP}."
            )
        )
    lines.append("")

    if not patterns:
        lines.append(_esc("Повторяющихся паттернов не найдено."))
    else:
        for p in patterns:
            pattern = p.get("pattern", "?")
            count = p.get("count", 0)
            desc = p.get("description", "")
            examples = p.get("examples", [])

            lines.append(f"🔁 *{_esc(str(pattern))}* — {count} сн\\.")
            if desc:
                lines.append(_esc(str(desc)))
            for ex in examples:
                lines.append(f"▸ {_esc(str(ex))}")
            lines.append("")

    await _send_result(update, "\n".join(lines))
