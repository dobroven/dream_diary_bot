import asyncio
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import db
from utils import _esc, MAG, dream_card

log = logging.getLogger(__name__)


async def cmd_search(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await update.message.reply_text(
            _esc(f"{MAG} Укажи ключевые слова:\n/search ключевое слово"),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    query = " ".join(ctx.args).strip()
    user_id = update.effective_user.id
    rows = await asyncio.to_thread(db.search_dreams, user_id, query)

    if not rows:
        await update.message.reply_text(
            f"{MAG} По запросу *{_esc(query)}* ничего не найдено\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    total = await asyncio.to_thread(db.count_dreams, user_id)
    prefetch_note = ""
    if total > 1000:
        prefetch_note = f"\n_Поиск среди последних 1000 снов из {total}\\. Если не нашёл \u2014 уточни запрос\\._"

    truncated = len(rows) >= 20
    header = f"{MAG} *Результаты поиска:* {_esc(query)} — {len(rows)} сн\\."
    if truncated:
        header += "\n_Показаны первые 20\\. Уточни запрос, если не нашёл нужный сон\\._"
    header += prefetch_note
    lines = [header + "\n"]
    for i, row in enumerate(rows, 1):
        lines.append(dream_card(row, index=i, list_mode=True, snippet_width=100))

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главная", callback_data="menu:main")]]),
    )


async def receive_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    awaiting = ctx.user_data.pop("awaiting", None)
    if not awaiting:
        await update.message.reply_text(
            _esc("❓ Неизвестная команда. Используйте /help или кнопку в главном меню."),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return
    if awaiting == "search":
        ctx.args = update.message.text.split()
        await cmd_search(update, ctx)
        return
