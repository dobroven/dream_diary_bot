import pytest
from unittest.mock import AsyncMock, MagicMock

from telegram import Update
from telegram.ext import ContextTypes

from handlers.map import STUB_TEXT, cmd_map


@pytest.mark.asyncio
async def test_cmd_map_stub_from_callback():
    """Нажатие кнопки «Карта снов» показывает заглушку."""
    query = MagicMock()
    query.edit_message_text = AsyncMock()

    update = MagicMock(spec=Update)
    update.callback_query = query
    ctx = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

    result = await cmd_map(update, ctx)

    assert result is None
    query.edit_message_text.assert_awaited_once_with(STUB_TEXT)


@pytest.mark.asyncio
async def test_cmd_map_stub_from_message():
    """Вызов без callback тоже показывает заглушку, а не падает."""
    msg = MagicMock()
    msg.reply_text = AsyncMock()

    update = MagicMock(spec=Update)
    update.callback_query = None
    update.message = msg
    ctx = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

    result = await cmd_map(update, ctx)

    assert result is None
    msg.reply_text.assert_awaited_once_with(STUB_TEXT)
