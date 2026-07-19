import asyncio
from textwrap import shorten

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler

import db
from utils import _esc, MOON, STAR, TITLE, DESCRIPTION


async def cmd_add(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message:
        await update.message.reply_text(
            _esc(f"{MOON} Новый сон.\n\nНапиши краткое название сна:"),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    else:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            _esc(f"{MOON} Новый сон.\n\nНапиши краткое название сна:"),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    return TITLE


async def received_title(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    title = update.message.text.strip()
    if not title:
        await update.message.reply_text(
            _esc("⚠️ Название не может быть пустым. Напиши краткое название сна:"),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return TITLE
    if len(title) > 120:
        await update.message.reply_text(
            _esc("⚠️ Название слишком длинное (макс. 120 символов). Попробуй ещё раз:"),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return TITLE

    ctx.user_data["dream_title"] = title
    await update.message.reply_text(
        _esc("Отлично! Теперь напиши описание сна — всё, что запомнилось:"),
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    return DESCRIPTION


async def received_description(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    description = update.message.text.strip()
    if not description:
        await update.message.reply_text(
            _esc("⚠️ Описание не может быть пустым. Напиши, что запомнилось из сна:"),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return DESCRIPTION
    if len(description) > 2000:
        await update.message.reply_text(
            _esc("⚠️ Описание слишком длинное (макс. 2000 символов). Сократи и попробуй снова:"),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return DESCRIPTION
    title = ctx.user_data.pop("dream_title", "—")
    user_id = update.effective_user.id

    dream_id = await asyncio.to_thread(db.add_dream, user_id, title, description)

    if dream_id is None:
        await update.message.reply_text(
            _esc("❌ Произошла ошибка при сохранении. Попробуй ещё раз."),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return ConversationHandler.END

    await update.message.reply_text(
        f"{STAR} {_esc('Сон сохранён!')}\n\n"
        f"{MOON} *{_esc(title)}*\n"
        f"{_esc(shorten(description, 200, placeholder='…'))}",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главная", callback_data="menu:main")]]),
    )
    return ConversationHandler.END
