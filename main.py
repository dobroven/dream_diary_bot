"""
Dream Diary Bot
───────────────
/start   — приветствие и справка
/add     — записать новый сон (диалог: название → описание)
/list    — список последних снов (с пагинацией)
/search  — поиск по ключевым словам
/delete  — удалить сон по названию
/edit    — редактировать сон
/map     — карта снов (анализ паттернов)
/cancel  — отменить текущее действие
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from telegram import Update
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
from utils import _esc, TITLE, DESCRIPTION, EDIT_TITLE, EDIT_DESC, EDIT_DATE

from handlers.menu import cmd_start, cmd_help, menu_callback
from handlers.add import cmd_add, received_title, received_description
from handlers.list import cmd_list, pagination_callback, view_callback, back_to_list_callback
from handlers.search import cmd_search, receive_text
from handlers.delete import cmd_delete
from handlers.edit import edit_callback, cmd_edit, edit_title, edit_desc, edit_date
from handlers.map import cmd_map

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)


async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data.clear()
    await update.message.reply_text(
        _esc("❌ Отменено."),
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    return ConversationHandler.END


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "Токен не найден. Создай файл .env рядом с main.py и добавь строку:\n"
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
    # /edit conversation
    edit_handler = ConversationHandler(
        entry_points=[
            CommandHandler("edit", cmd_edit),
            CallbackQueryHandler(edit_callback, pattern=r"^edit:\d+$"),
        ],
        states={
            EDIT_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_title)],
            EDIT_DESC:  [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_desc)],
            EDIT_DATE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_date)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
    )
    app.add_handler(edit_handler)

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text))

    log.info("Бот запущен")
    app.run_polling(allowed_updates=Update.ALL_TYPES, bootstrap_retries=-1)


if __name__ == "__main__":
    main()
