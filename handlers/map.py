import logging

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

log = logging.getLogger(__name__)

STUB_TEXT = "🚧 Карта снов в разработке. Загляни позже."


async def cmd_map(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Заглушка: функция временно отключена.

    Код генерации карты остался в ai.py и prompts/ — его можно вернуть,
    когда фича снова понадобится.
    """
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(STUB_TEXT)
        except BadRequest as e:
            # Например, «message is not modified» при повторном нажатии
            # на старую кнопку.
            log.debug("Не удалось обновить сообщение заглушки: %s", e)
    else:
        await update.message.reply_text(STUB_TEXT)
