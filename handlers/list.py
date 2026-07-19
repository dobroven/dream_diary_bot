import asyncio
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import db
from utils import _esc, MOON, BOOK, PAGE_SIZE, dream_card

log = logging.getLogger(__name__)


async def cmd_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    await _send_list_page(update, ctx, user_id, offset=0)


async def _send_list_page(
    update: Update,
    ctx: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    offset: int,
) -> None:
    ctx.user_data["list_offset"] = offset
    total = await asyncio.to_thread(db.count_dreams, user_id)
    if total == 0:
        text = _esc(f"{BOOK} У тебя пока нет записанных снов. Начни с /add!")
        if update.callback_query:
            await update.callback_query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN_V2)
        else:
            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2)
        return
    rows = await asyncio.to_thread(db.list_dreams, user_id, PAGE_SIZE, offset)
    lines = [f"{BOOK} *Твои сны* \\({total} всего\\)\n"]
    buttons: list[list[InlineKeyboardButton]] = []
    for i, row in enumerate(rows, start=offset + 1):
        lines.append(dream_card(row, index=i, list_mode=True, snippet_width=80))
        buttons.append([InlineKeyboardButton(f"Читать {i}", callback_data=f"view:{row['id']}")])
    if offset > 0:
        buttons.append([InlineKeyboardButton("◀ Назад", callback_data=f"list:{offset - PAGE_SIZE}")])
    if offset + PAGE_SIZE < total:
        buttons.append([InlineKeyboardButton("Далее ▶", callback_data=f"list:{offset + PAGE_SIZE}")])
    buttons.append([InlineKeyboardButton("🏠 Главная", callback_data="menu:main")])
    text = "\n".join(lines)
    markup = InlineKeyboardMarkup(buttons) if buttons else None
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=markup)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=markup)
    return


async def pagination_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    _, offset_str = query.data.split(":")
    try:
        offset = int(offset_str)
    except ValueError:
        offset = 0
    offset = max(0, offset)
    user_id = update.effective_user.id
    await _send_list_page(update, ctx, user_id, offset=offset)


async def view_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    log.info("view_callback triggered: %s", query.data)
    try:
        dream_id = int(query.data.split(":")[1])
        user_id = update.effective_user.id
        row = await asyncio.to_thread(db.get_dream, user_id, dream_id)
        if not row:
            await query.edit_message_text(
                _esc("⚠️ Сон не найден или не принадлежит вам."),
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            return
        text = dream_card(row)
        edit_button = InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit:{dream_id}")
        delete_button = InlineKeyboardButton("🗑 Удалить", callback_data=f"delete:{dream_id}")
        back_button = InlineKeyboardButton("◀️ Назад к списку", callback_data="back_to_list")
        markup = InlineKeyboardMarkup([[edit_button, delete_button], [back_button]])
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=markup)
    except Exception as e:
        log.exception("Ошибка в view_callback: %s", e)
        await query.edit_message_text(
            _esc("❗ Произошла ошибка при загрузке сна. Пожалуйста, попробуйте ещё раз."),
            parse_mode=ParseMode.MARKDOWN_V2,
        )


async def back_to_list_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    offset = ctx.user_data.get("list_offset", 0)
    await _send_list_page(update, ctx, user_id, offset=offset)
