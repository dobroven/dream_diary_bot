import asyncio
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import ai
import db
from utils import BOOK

log = logging.getLogger(__name__)

MODEL_LABEL = "🧠 DeepSeek V3"


async def cmd_map(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.callback_query:
        await update.message.reply_text("🗺 Используй кнопку «Карта снов» в главном меню.")
        return

    query = update.callback_query
    user_id = update.effective_user.id
    total = await asyncio.to_thread(db.count_dreams, user_id)
    if total == 0:
        await query.edit_message_text(
            f"{BOOK} Сначала запиши хотя бы один сон через кнопку «Добавить».",
            parse_mode=ParseMode.HTML,
        )
        return

    await query.edit_message_text(
        f"🗺 {MODEL_LABEL} — составляю карту твоих снов… это может занять до минуты.",
        parse_mode=ParseMode.HTML,
    )

    try:
        patterns = await asyncio.to_thread(ai.generate_dream_map, user_id)
    except Exception as e:
        log.exception("Ошибка при генерации карты снов: %s", e)
        await query.edit_message_text(
            "❌ Произошла ошибка при составлении карты. Попробуй позже.",
            parse_mode=ParseMode.HTML,
        )
        return

    if not patterns:
        await query.edit_message_text(
            "🗺 Повторяющихся паттернов не найдено. Добавь ещё снов и попробуй снова.",
            parse_mode=ParseMode.HTML,
        )
        return

    lines = [f"🗺 <b>Карта сновидений</b> ({MODEL_LABEL})\nВсего снов: {total}\n"]
    for p in patterns:
        pattern = p.get("pattern", "?")
        count = p.get("count", 0)
        desc = p.get("description", "")
        examples = p.get("examples", [])
        lines.append(f"🔁 <b>{pattern}</b> — {count} сн.")
        if desc:
            lines.append(desc)
        for ex in examples:
            lines.append(f"▸ {ex}")
        lines.append("")

    text = "\n".join(lines)

    markup = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главная", callback_data="menu:main")]])
    if len(text) <= 4096:
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
        return

    parts = []
    while len(text) > 4096:
        idx = text.rfind("\n", 0, 4096)
        if idx == -1:
            idx = 4096
        parts.append(text[:idx])
        text = text[idx:].lstrip("\n")
    parts.append(text)

    await query.edit_message_text(parts[0], parse_mode=ParseMode.HTML)
    for part in parts[1:]:
        await query.message.reply_text(part, parse_mode=ParseMode.HTML)
