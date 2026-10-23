from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from openai import RateLimitError

from handlers.map import cmd_map


def _callback_update():
    query = MagicMock()
    query.edit_message_text = AsyncMock()
    query.message.reply_text = AsyncMock()
    update = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=1),
        message=None,
    )
    return update, query


def _message_update():
    message = MagicMock()
    message.reply_text = AsyncMock()
    update = SimpleNamespace(
        callback_query=None,
        effective_user=SimpleNamespace(id=1),
        message=message,
    )
    return update, message


def _rate_limit_error() -> RateLimitError:
    request = httpx.Request("POST", "https://api.zveno.ai/v1/chat/completions")
    response = httpx.Response(429, request=request)
    return RateLimitError("daily limit", response=response, body=None)


@pytest.mark.asyncio
async def test_cmd_map_without_dreams_shows_hint():
    update, query = _callback_update()
    ctx = SimpleNamespace(user_data={})

    with patch("handlers.map.db.count_dreams", return_value=0), \
         patch("handlers.map.ai.generate_dream_map") as generate:
        await cmd_map(update, ctx)

    generate.assert_not_called()
    query.edit_message_text.assert_awaited_once()
    text = query.edit_message_text.call_args.kwargs["text"]
    assert "Сначала запиши" in text
    assert query.edit_message_text.call_args.kwargs["reply_markup"] is not None


@pytest.mark.asyncio
async def test_cmd_map_success_renders_patterns():
    update, query = _callback_update()
    ctx = SimpleNamespace(user_data={})
    patterns = [
        {
            "pattern": "полёт",
            "count": 3,
            "examples": ["лечу над городом", "полёт над морем"],
            "description": "Полёты во сне.",
        }
    ]

    with patch("handlers.map.db.count_dreams", return_value=5), \
         patch("handlers.map.ai.generate_dream_map", return_value=patterns):
        await cmd_map(update, ctx)

    assert query.edit_message_text.await_count == 2
    result = query.edit_message_text.await_args_list[-1].kwargs
    assert "Карта сновидений" in result["text"]
    assert "полёт" in result["text"]
    assert "3 сн\\." in result["text"]
    assert "лечу над городом" in result["text"]
    assert "Всего снов: 5" in result["text"]
    assert result["reply_markup"] is not None


@pytest.mark.asyncio
async def test_cmd_map_without_patterns_shows_empty_state():
    update, query = _callback_update()
    ctx = SimpleNamespace(user_data={})

    with patch("handlers.map.db.count_dreams", return_value=2), \
         patch("handlers.map.ai.generate_dream_map", return_value=[]):
        await cmd_map(update, ctx)

    text = query.edit_message_text.await_args_list[-1].kwargs["text"]
    assert "Повторяющихся паттернов не найдено" in text
    assert query.edit_message_text.await_args_list[-1].kwargs["reply_markup"] is not None


@pytest.mark.asyncio
async def test_cmd_map_handles_unexpected_error():
    update, query = _callback_update()
    ctx = SimpleNamespace(user_data={})

    with patch("handlers.map.db.count_dreams", return_value=2), \
         patch("handlers.map.ai.generate_dream_map", side_effect=RuntimeError("boom")):
        await cmd_map(update, ctx)

    text = query.edit_message_text.await_args_list[-1].kwargs["text"]
    assert "Произошла ошибка" in text


@pytest.mark.asyncio
async def test_cmd_map_handles_rate_limit():
    update, query = _callback_update()
    ctx = SimpleNamespace(user_data={})

    with patch("handlers.map.db.count_dreams", return_value=2), \
         patch("handlers.map.ai.generate_dream_map", side_effect=_rate_limit_error()):
        await cmd_map(update, ctx)

    text = query.edit_message_text.await_args_list[-1].kwargs["text"]
    assert "Лимит бесплатной модели" in text


@pytest.mark.asyncio
async def test_cmd_map_works_as_command():
    update, message = _message_update()
    ctx = SimpleNamespace(user_data={})

    with patch("handlers.map.db.count_dreams", return_value=0):
        await cmd_map(update, ctx)

    message.reply_text.assert_awaited_once()
    assert "Сначала запиши" in message.reply_text.call_args.kwargs["text"]


@pytest.mark.asyncio
async def test_cmd_map_splits_long_result():
    update, query = _callback_update()
    ctx = SimpleNamespace(user_data={})
    patterns = [
        {
            "pattern": "длинный паттерн",
            "count": 100,
            "examples": ["пример номер один с несколькими словами"] * 100,
            "description": "Описание.",
        }
    ]

    with patch("handlers.map.db.count_dreams", return_value=100), \
         patch("handlers.map.ai.generate_dream_map", return_value=patterns):
        await cmd_map(update, ctx)

    assert query.message.reply_text.await_count >= 1
    last = query.message.reply_text.await_args_list[-1].kwargs
    assert last["reply_markup"] is not None
