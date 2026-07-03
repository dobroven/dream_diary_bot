"""
Dream Diary Bot
───────────────
/start   — приветствие и справка
/add     — записать новый сон (диалог: название → описание)
/list    — список последних снов (с пагинацией)
/search  — поиск по ключевым словам
/delete  — удалить сон по названию
/cancel  — отменить текущее действие
"""

import logging
import os
from pathlib import Path
from textwrap import shorten

from dotenv import load_dotenv

# Загружаем .env из папки рядом с bot.py (работает и при запуске из другой директории)
load_dotenv(Path(__file__).parent / ".env")

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.request import HTTPXRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import db

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ── Conversation states ───────────────────────────────────────────────────────
TITLE, DESCRIPTION = range(2)

# ── Pagination page size ──────────────────────────────────────────────────────
PAGE_SIZE = 5

# ── Helpers ───────────────────────────────────────────────────────────────────
MOON = "🌙"
STAR = "✨"
BOOK = "📖"
MAG  = "🔍"
TRASH = "🗑"


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


def _esc(text: str) -> str:
    """Escape MarkdownV2 special characters (except asterisks for formatting)."""
    # Full set of MarkdownV2 reserved characters:
    # _ * [ ] ( ) ~ ` > # + - = | { } . !
    # We intentionally keep '*' unescaped because we use it for bold formatting.
    for char in ['_', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']:
        text = text.replace(char, f'\\{char}')
    return text


# ── /start ────────────────────────────────────────────────────────────────────
def main_menu_markup() -> InlineKeyboardMarkup:
    """Return InlineKeyboardMarkup with main menu buttons in two rows."""
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
    """Подробная справка по командам."""
    text = (
        f"{BOOK} *Dream Diary Bot — справка*\n\n"
        f"*/start* — главное меню\n"
        f"*/add* — записать новый сон (название → описание)\n"
        f"*/list* — список последних снов (с пагинацией)\n"
        f"*/search <запрос>* — поиск по ключевым словам\n"
        f"*/delete <#N|название>* — удалить сон по номеру или названию\n"
        f"*/cancel* — отменить текущее действие\n"
        f"*/help* — эта справка\n\n"
        f"Также можно пользоваться кнопками в главном меню 🏠"
    )
    if update.message:
        await update.message.reply_text(
            _esc(text),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    else:
        query = update.callback_query
        await query.answer()
        await query.message.reply_text(
            _esc(text),
            parse_mode=ParseMode.MARKDOWN_V2,
        )


# ── /add — ConversationHandler ────────────────────────────────────────────────
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

    dream_id = db.add_dream(user_id, title, description)

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


async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data.clear()
    await update.message.reply_text(
        _esc("❌ Отменено."),
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    return ConversationHandler.END


# ── /list — paginated ─────────────────────────────────────────────────────────
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
    total = db.count_dreams(user_id)
    if total == 0:
        text = _esc(f"{BOOK} У тебя пока нет записанных снов. Начни с /add!")
        if update.callback_query:
            await update.callback_query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN_V2)
        else:
            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2)
        return
    rows = db.list_dreams(user_id, limit=PAGE_SIZE, offset=offset)
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



# ── View full dream callback ────────────────────────────────────────────────
async def view_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    # Acknowledge callback to avoid loading spinner
    await query.answer()
    # Log callback data for debugging
    log.info("view_callback triggered: %s", query.data)
    try:
        dream_id = int(query.data.split(":")[1])
        user_id = update.effective_user.id
        row = db.get_dream(user_id, dream_id)
        if not row:
            await query.edit_message_text(
                _esc("⚠️ Сон не найден или не принадлежит вам."),
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            return
        text = dream_card(row)
        back_button = InlineKeyboardButton("◀️ Назад к списку", callback_data="back_to_list")
        markup = InlineKeyboardMarkup([[back_button]])
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=markup)
    except Exception as e:
        log.exception("Ошибка в view_callback: %s", e)
        await query.edit_message_text(
            _esc("❗ Произошла ошибка при загрузке сна. Пожалуйста, попробуйте ещё раз."),
            parse_mode=ParseMode.MARKDOWN_V2,
        )

# ── Back to list callback ───────────────────────────────────────────────────────
async def back_to_list_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    # Return to first page (offset 0). Could preserve previous offset, but simple reset.
    await _send_list_page(update, ctx, user_id, offset=0)

# ── Menu callback handling ───────────────────────────────────────────────
async def menu_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    action = query.data.split(":")[1]

    if action == "main":
        await cmd_start(update, ctx)
        return
    if action == "add":
        # Start add conversation via callback
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

# ── Generic text receiver for search / delete after button press ───────────────
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
    if awaiting == "delete":
        ctx.args = [update.message.text.strip()]
        await cmd_delete(update, ctx)
        return

async def cmd_search(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await update.message.reply_text(
            _esc(f"{MAG} Укажи ключевые слова:\n/search ключевое слово"),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    query = " ".join(ctx.args).strip()
    user_id = update.effective_user.id
    rows = db.search_dreams(user_id, query)

    if not rows:
        await update.message.reply_text(
            f"{MAG} По запросу *{_esc(query)}* ничего не найдено\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    total = db.count_dreams(user_id)
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


# ── /delete ───────────────────────────────────────────────────────────────────
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


# ── Bootstrap ─────────────────────────────────────────────────────────────────
def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "Токен не найден. Создай файл .env рядом с bot.py и добавь строку:\n"
            "TELEGRAM_BOT_TOKEN=ваш_токен_здесь"
        )

    db.init_db()
    log.info("База данных инициализирована")

    proxy_url = os.environ.get("PROXY_URL", "").strip()
    if proxy_url:
        request = HTTPXRequest(proxy=proxy_url, connect_timeout=30, read_timeout=30, write_timeout=30, pool_timeout=30)
        builder = Application.builder().token(token).request(request).get_updates_request(request)
        log.info("Прокси: %s", proxy_url)
    else:
        builder = Application.builder().token(token)
    app = builder.build()

    # /add conversation
    add_handler = ConversationHandler(
        entry_points=[
            CommandHandler("add", cmd_add),
            CallbackQueryHandler(cmd_add, pattern=r"^menu:add$"),
        ],
        states={
            TITLE:       [MessageHandler(filters.TEXT & ~filters.COMMAND, received_title)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_description)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help",  cmd_help))
    app.add_handler(add_handler)
    app.add_handler(CommandHandler("list",   cmd_list))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(CommandHandler("delete", cmd_delete))
    app.add_handler(CallbackQueryHandler(menu_callback, pattern=r"^menu:"))
    app.add_handler(CallbackQueryHandler(view_callback, pattern=r"^view:"))
    app.add_handler(CallbackQueryHandler(back_to_list_callback, pattern=r"^back_to_list$"))
    app.add_handler(CallbackQueryHandler(pagination_callback, pattern=r"^list:\d+$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text))

    log.info("Бот запущен")
    app.run_polling(allowed_updates=Update.ALL_TYPES, bootstrap_retries=-1)


if __name__ == "__main__":
    main()
