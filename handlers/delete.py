import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import db
from utils import _esc, TRASH, PAGE_SIZE

log = logging.getLogger(__name__)


async def cmd_delete(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args or not ctx.args[0].strip():
        await update.message.reply_text(
            _esc(f"{TRASH} Укажи номер сна для удаления (пример: #1):"),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    input_text = ctx.args[0].strip()
    user_id = update.effective_user.id

    if input_text.startswith('#'):
        try:
            idx = int(input_text.lstrip('#'))
        except ValueError:
            await update.message.reply_text(
                _esc(f"{TRASH} Укажи корректный номер сна (пример: #1)."),
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            return

        offset = ctx.user_data.get("list_offset", 0)
        rows = db.list_dreams(user_id, limit=PAGE_SIZE, offset=offset)
        page_index = idx - offset - 1
        if 0 <= page_index < len(rows):
            dream_id = rows[page_index]['id']
            deleted = db.delete_dream(user_id, dream_id)
        else:
            await update.message.reply_text(
                _esc(f"⚠️ Сон с номером #{idx} не найден на текущей странице. Перелистай список и попробуй снова."),
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            return
    else:
        title = input_text
        count = db.count_dreams_by_title(user_id, title)
        if count == 0:
            await update.message.reply_text(
                _esc(f"⚠️ Сон с названием *{_esc(title)}* не найден."),
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главная", callback_data="menu:main")]]),
            )
            return
        if count > 1:
            await update.message.reply_text(
                _esc(f"⚠️ Найдено {count} снов с таким названием. Используй номер из списка, например #1."),
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главная", callback_data="menu:main")]]),
            )
            return
        deleted = db.delete_dream_by_title(user_id, title)

    if deleted:
        await update.message.reply_text(
            _esc(f"{TRASH} Сон удалён."),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главная", callback_data="menu:main")]]),
        )
    else:
        await update.message.reply_text(
            _esc(f"⚠️ Сон не найден или не принадлежит тебе."),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главная", callback_data="menu:main")]]),
        )
