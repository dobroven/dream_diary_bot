import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from utils import _esc, MOON, MAG, TRASH, BOOK

from handlers.add import cmd_add
from handlers.list import cmd_list
from handlers.map import cmd_map

log = logging.getLogger(__name__)


def main_menu_markup() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("📥 Добавить", callback_data="menu:add"),
        ],
        [
            InlineKeyboardButton("📄 Список", callback_data="menu:list"),
            InlineKeyboardButton("🔍 Поиск", callback_data="menu:search"),
        ],
        [
            InlineKeyboardButton("🗑 Удалить", callback_data="menu:delete"),
            InlineKeyboardButton("🗺 Карта снов", callback_data="menu:map"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(
            _esc(f"{MOON} Дневник сновидений.\n\nЗаписывай, ищи и перечитывай свои сны."),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=main_menu_markup(),
        )
    else:
        query = update.callback_query
        await query.answer()
        await query.message.reply_text(
            _esc(f"{MOON} Дневник сновидений.\n\nЗаписывай, ищи и перечитывай свои сны."),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=main_menu_markup(),
        )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        f"{BOOK} <b>Dream Diary Bot — справка</b>\n\n"
        f"/start — главное меню\n"
        f"/add — записать новый сон (название → описание)\n"
        f"/list — список последних снов (с пагинацией)\n"
        f"/search &lt;запрос&gt; — поиск по ключевым словам\n"
        f"/delete &lt;#N|название&gt; — удалить сон по номеру или названию\n"
        f"/cancel — отменить текущее действие\n"
        f"/help — эта справка\n\n"
        f"Также можно пользоваться кнопками в главном меню 🏠"
    )
    if update.message:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    else:
        query = update.callback_query
        await query.answer()
        await query.message.reply_text(text, parse_mode=ParseMode.HTML)


async def menu_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    action = query.data.split(":")[1]

    if action == "main":
        await cmd_start(update, ctx)
        return
    if action == "add":
        await cmd_add(update, ctx)
        return
    if action == "list":
        await cmd_list(update, ctx)
        return
    if action == "search":
        ctx.user_data.clear()
        ctx.user_data["awaiting"] = "search"
        await query.edit_message_text(
            _esc(f"{MAG} Введите запрос для поиска:\n"),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return
    if action == "delete":
        ctx.user_data.clear()
        ctx.user_data["awaiting"] = "delete"
        await query.edit_message_text(
            _esc(f"{TRASH} Введите номер сна (например, #1) для удаления:\n"),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return
    if action == "map":
        await cmd_map(update, ctx)
        return
