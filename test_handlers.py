import pytest
from unittest.mock import AsyncMock, MagicMock

from telegram import Update
from telegram.ext import ContextTypes

from handlers.map import cmd_map


@pytest.mark.asyncio
async def test_cmd_map_no_callback():
    """cmd_map should reply and return early when called without callback_query."""
    msg = MagicMock()
    msg.reply_text = AsyncMock()

    update = MagicMock(spec=Update)
    update.callback_query = None
    update.message = msg
    ctx = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

    result = await cmd_map(update, ctx)

    assert result is None
    msg.reply_text.assert_awaited_once_with("🗺 Используй кнопку «Карта снов» в главном меню.")
