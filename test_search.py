from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import Update
from telegram.ext import ConversationHandler

from handlers.menu import menu_callback
from handlers.search import cmd_search, receive_text
from main import cmd_cancel


@pytest.mark.asyncio
async def test_empty_search_keeps_search_mode():
    update = MagicMock(spec=Update)
    update.message.reply_text = AsyncMock()
    update.effective_user.id = 1
    ctx = SimpleNamespace(user_data={}, args=["единорог"])

    with patch("handlers.search.db.search_dreams", return_value=[]):
        result = await cmd_search(update, ctx)

    assert result is None
    assert ctx.user_data["awaiting"] == "search"
    text = update.message.reply_text.call_args.args[0]
    assert "ничего не найдено" in text
    assert "Главная" in text
    assert "Главная»\\." in text
    assert "/cancel" not in text
    assert update.message.reply_text.call_args.kwargs["reply_markup"] is not None


@pytest.mark.asyncio
async def test_next_message_runs_search_without_reopening_menu():
    update = MagicMock(spec=Update)
    update.message.text = "замок"
    update.message.reply_text = AsyncMock()
    update.effective_user.id = 1
    ctx = SimpleNamespace(user_data={"awaiting": "search"}, args=[])

    with patch("handlers.search.db.search_dreams", return_value=[]) as search:
        await receive_text(update, ctx)

    search.assert_called_once_with(1, "замок")
    assert ctx.user_data["awaiting"] == "search"


@pytest.mark.asyncio
async def test_search_without_args_enters_search_mode():
    update = MagicMock(spec=Update)
    update.message.reply_text = AsyncMock()
    ctx = SimpleNamespace(user_data={}, args=[])

    await cmd_search(update, ctx)

    assert ctx.user_data["awaiting"] == "search"
    assert update.message.reply_text.await_count == 1


@pytest.mark.asyncio
async def test_successful_search_clears_search_mode():
    update = MagicMock(spec=Update)
    update.message.reply_text = AsyncMock()
    update.effective_user.id = 1
    ctx = SimpleNamespace(user_data={"awaiting": "search"}, args=["сон"])

    with patch("handlers.search.db.search_dreams", return_value=[MagicMock()]), \
         patch("handlers.search.db.count_dreams", return_value=1), \
         patch("handlers.search.dream_card", return_value="card"):
        await cmd_search(update, ctx)

    assert "awaiting" not in ctx.user_data
    assert "Результаты поиска" in update.message.reply_text.call_args.args[0]


@pytest.mark.asyncio
async def test_main_menu_clears_search_mode():
    query = MagicMock()
    query.data = "menu:main"
    query.answer = AsyncMock()
    update = MagicMock(spec=Update)
    update.callback_query = query
    ctx = SimpleNamespace(user_data={"awaiting": "search"}, args=[])

    with patch("handlers.menu.cmd_start", new=AsyncMock()) as start:
        await menu_callback(update, ctx)

    assert "awaiting" not in ctx.user_data
    start.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancel_clears_user_data():
    update = MagicMock(spec=Update)
    update.message.reply_text = AsyncMock()
    ctx = SimpleNamespace(user_data={"awaiting": "search"})

    result = await cmd_cancel(update, ctx)

    assert result == ConversationHandler.END
    assert ctx.user_data == {}
