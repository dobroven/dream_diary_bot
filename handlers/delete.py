import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import db
from utils import _esc, TRASH, PAGE_SIZE, dream_card

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
            row = rows[page_index]
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
        row = db.get_dream_by_title(user_id, title)
        if not row:
            await update.message.reply_text(
                _esc("⚠️ Сон не найден."),
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            return

    await _send_delete_confirm(update, ctx, user_id, row)


async def delete_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    dream_id = int(query.data.split(":")[1])
    user_id = update.effective_user.id
    row = db.get_dream(user_id, dream_id)
    if not row:
        await query.edit_message_text(
            _esc("⚠️ Сон не найден."),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return
    await _send_delete_confirm(update, ctx, user_id, row)


async def _send_delete_confirm(
    update: Update, ctx: ContextTypes.DEFAULT_TYPE, user_id: int, row
) -> None:
    text = (
        f"{TRASH} *Удалить сон?*\n\n"
        f"{dream_card(row)}\n\n"
        f"{_esc('Это действие необратимо.')}"
    )
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🗑 Да, удалить", callback_data=f"confirm_delete:{row['id']}:yes"),
            InlineKeyboardButton("↩️ Нет", callback_data=f"confirm_delete:{row['id']}:no"),
        ],
    ])
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=markup)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=markup)


async def confirm_delete_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    action = parts[1]
    dream_id = int(parts[2])
    user_id = update.effective_user.id

    if action == "no":
        row = db.get_dream(user_id, dream_id)
        if not row:
            await query.edit_message_text(
                _esc("⚠️ Сон не найден."),
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            return
        text = dream_card(row)
        edit_button = InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit:{dream_id}")
        delete_button = InlineKeyboardButton("🗑 Удалить", callback_data=f"delete:{dream_id}")
        back_button = InlineKeyboardButton("◀️ Назад к списку", callback_data="back_to_list")
        markup = InlineKeyboardMarkup([[edit_button, delete_button], [back_button]])
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=markup)
        return

    deleted = db.delete_dream(user_id, dream_id)
    if deleted:
        await query.edit_message_text(
            _esc(f"{TRASH} Сон удалён."),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главная", callback_data="menu:main")]]),
        )
    else:
        await query.edit_message_text(
            _esc(f"⚠️ Сон не найден или не принадлежит тебе."),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главная", callback_data="menu:main")]]),
        )
