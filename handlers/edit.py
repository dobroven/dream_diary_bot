import asyncio
import logging
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler

import db
from utils import _esc, EDIT_TITLE, EDIT_DESC, EDIT_DATE, PAGE_SIZE

log = logging.getLogger(__name__)


async def edit_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    dream_id = int(query.data.split(":")[1])
    user_id = update.effective_user.id
    row = await asyncio.to_thread(db.get_dream, user_id, dream_id)
    if not row:
        await query.edit_message_text(
            _esc("⚠️ Сон не найден или не принадлежит вам."),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return ConversationHandler.END

    ctx.user_data["edit_dream_id"] = dream_id
    ctx.user_data["edit_title"] = row["title"]
    ctx.user_data["edit_desc"] = row["description"]
    ctx.user_data["edit_date"] = row["date"]

    current = (
        f"✏️ *Редактирование сна*\n\n"
        f"Текущее название: *{_esc(row['title'])}*\n"
        f"Текущее описание: {_esc(row['description'])}\n"
        f"Текущая дата: {_esc(row['date'])}\n\n"
        f"Напиши новое название {_esc('(или отправь «.» чтобы оставить текущее):')}"
    )
    await query.edit_message_text(current, parse_mode=ParseMode.MARKDOWN_V2)
    return EDIT_TITLE


async def cmd_edit(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    if not ctx.args or not ctx.args[0].strip():
        await update.message.reply_text(
            _esc("✏️ Укажи номер сна ") + _esc("(например: /edit #1):"),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return ConversationHandler.END

    input_text = ctx.args[0].strip()
    user_id = update.effective_user.id

    if input_text.startswith("#"):
        try:
            idx = int(input_text.lstrip("#"))
        except ValueError:
            await update.message.reply_text(
                _esc("✏️ Укажи корректный номер сна (пример: /edit #1)."),
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            return ConversationHandler.END
        offset = ctx.user_data.get("list_offset", 0)
        rows = await asyncio.to_thread(db.list_dreams, user_id, PAGE_SIZE, offset)
        page_index = idx - offset - 1
        if 0 <= page_index < len(rows):
            dream_id = rows[page_index]["id"]
        else:
            await update.message.reply_text(
                _esc(f"⚠️ Сон с номером #{idx} не найден на текущей странице."),
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            return ConversationHandler.END
    else:
        title = input_text
        count = await asyncio.to_thread(db.count_dreams_by_title, user_id, title)
        if count == 0:
            await update.message.reply_text(
                _esc(f"⚠️ Сон с названием *{_esc(title)}* не найден."),
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главная", callback_data="menu:main")]]),
            )
            return ConversationHandler.END
        if count > 1:
            await update.message.reply_text(
                _esc(f"⚠️ Найдено {count} снов с таким названием. Используй номер, например #1."),
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            return ConversationHandler.END
        row = await asyncio.to_thread(db.get_dream_by_title, user_id, title)
        if not row:
            await update.message.reply_text(
                _esc("⚠️ Сон не найден."),
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            return ConversationHandler.END
        dream_id = row["id"]

    row = await asyncio.to_thread(db.get_dream, user_id, dream_id)
    ctx.user_data["edit_dream_id"] = dream_id
    ctx.user_data["edit_title"] = row["title"]
    ctx.user_data["edit_desc"] = row["description"]
    ctx.user_data["edit_date"] = row["date"]

    current = (
        f"✏️ *Редактирование сна*\n\n"
        f"Текущее название: *{_esc(row['title'])}*\n"
        f"Текущее описание: {_esc(row['description'])}\n"
        f"Текущая дата: {_esc(row['date'])}\n\n"
        f"Напиши новое название {_esc('(или отправь «.» чтобы оставить текущее):')}"
    )
    await update.message.reply_text(current, parse_mode=ParseMode.MARKDOWN_V2)
    return EDIT_TITLE


async def edit_title(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text and text != ".":
        if len(text) > 120:
            await update.message.reply_text(
                _esc("⚠️ Название слишком длинное (макс. 120 символов). Попробуй ещё раз:"),
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            return EDIT_TITLE
        ctx.user_data["edit_title"] = text
    await update.message.reply_text(
        _esc(f"Название: *{_esc(ctx.user_data['edit_title'])}*\n\nТеперь напиши описание (или «.» чтобы оставить текущее):"),
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    return EDIT_DESC


async def edit_desc(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text and text != ".":
        if len(text) > 2000:
            await update.message.reply_text(
                _esc("⚠️ Описание слишком длинное (макс. 2000 символов). Попробуй ещё раз:"),
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            return EDIT_DESC
        ctx.user_data["edit_desc"] = text
    current_date = ctx.user_data["edit_date"]
    await update.message.reply_text(
        _esc(f"Описание сохранено.\n\nТекущая дата: {current_date}\nНапиши новую дату в формате ДД.ММ.ГГГГ или ГГГГ-ММ-ДД (или «.» чтобы оставить):"),
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    return EDIT_DATE


def _parse_date(raw: str) -> str | None:
    raw = raw.strip()
    if not raw or raw == ".":
        return None
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d.%m.%y"):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


async def edit_date(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    raw = update.message.text.strip()
    parsed = _parse_date(raw)
    if raw != "." and parsed is None:
        await update.message.reply_text(
            _esc("⚠️ Неверный формат даты. Используй ДД.ММ.ГГГГ или ГГГГ-ММ-ДД (или «.» чтобы оставить):"),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return EDIT_DATE

    if parsed:
        ctx.user_data["edit_date"] = parsed

    user_id = update.effective_user.id
    dream_id = ctx.user_data["edit_dream_id"]
    title = ctx.user_data["edit_title"]
    desc = ctx.user_data["edit_desc"]
    dream_date = ctx.user_data["edit_date"]

    ok = await asyncio.to_thread(db.update_dream, user_id, dream_id, title, desc, dream_date)
    if not ok:
        await update.message.reply_text(
            _esc("❌ Произошла ошибка при сохранении. Попробуй ещё раз."),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return ConversationHandler.END

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Назад к списку", callback_data="back_to_list")],
        [InlineKeyboardButton("🏠 Главная", callback_data="menu:main")],
    ])
    await update.message.reply_text(
        f"✅ *Сон обновлён*\n\n"
        f"*{_esc(title)}*\n"
        f"📅 {_esc(dream_date)}",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=markup,
    )
    return ConversationHandler.END
