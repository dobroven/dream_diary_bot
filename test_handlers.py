import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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


def _cached(
    patterns=None,
    dreams_count=14,
    period_start="2026-09-27",
    period_end="2026-10-19",
    generated_at="2026-10-26T09:00:00",
):
    return {
        "patterns_json": json.dumps(patterns or [], ensure_ascii=False),
        "dreams_count": dreams_count,
        "period_start": period_start,
        "period_end": period_end,
        "generated_at": generated_at,
    }


@pytest.mark.asyncio
async def test_cmd_map_without_dreams_shows_minimum_hint():
    update, query = _callback_update()
    ctx = SimpleNamespace(user_data={})

    with patch("handlers.map.db.count_dreams", return_value=0), \
         patch("handlers.map.db.get_dream_map", return_value=None):
        await cmd_map(update, ctx)

    query.edit_message_text.assert_awaited_once()
    text = query.edit_message_text.call_args.kwargs["text"]
    assert "минимум 10" in text
    assert "Сейчас: 0" in text
    assert query.edit_message_text.call_args.kwargs["reply_markup"] is not None


@pytest.mark.asyncio
async def test_cmd_map_without_cache_with_enough_dreams_reports_pending():
    update, query = _callback_update()
    ctx = SimpleNamespace(user_data={})

    with patch("handlers.map.db.count_dreams", return_value=12), \
         patch("handlers.map.db.get_dream_map", return_value=None):
        await cmd_map(update, ctx)

    text = query.edit_message_text.call_args.kwargs["text"]
    assert "ещё не составлена" in text
    assert "автоматического обновления" in text


@pytest.mark.asyncio
async def test_cmd_map_reads_cached_result_with_dates():
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

    with patch("handlers.map.db.count_dreams", return_value=25), \
         patch("handlers.map.db.get_dream_map", return_value=_cached(patterns)):
        await cmd_map(update, ctx)

    query.edit_message_text.assert_awaited_once()
    result = query.edit_message_text.await_args.kwargs
    text = result["text"]
    assert "Карта сновидений" in text
    assert "Обновлено: 26\\.10\\.2026" in text
    assert "27\\.09\\.2026 — 19\\.10\\.2026" in text
    assert "Всего снов: 25 · в анализ вошло: 14" in text
    assert "полёт" in text
    assert "3 сн\\." in text
    assert "лечу над городом" in text
    assert result["reply_markup"] is not None


@pytest.mark.asyncio
async def test_cmd_map_with_cached_empty_result_shows_empty_state():
    update, query = _callback_update()
    ctx = SimpleNamespace(user_data={})

    with patch("handlers.map.db.count_dreams", return_value=10), \
         patch("handlers.map.db.get_dream_map", return_value=_cached([])):
        await cmd_map(update, ctx)

    text = query.edit_message_text.await_args.kwargs["text"]
    assert "Повторяющихся паттернов не найдено" in text
    assert query.edit_message_text.await_args.kwargs["reply_markup"] is not None


@pytest.mark.asyncio
async def test_cmd_map_shows_old_cache_below_minimum_with_note():
    update, query = _callback_update()
    ctx = SimpleNamespace(user_data={})
    patterns = [{"pattern": "вода", "count": 2, "examples": [], "description": ""}]

    with patch("handlers.map.db.count_dreams", return_value=5), \
         patch("handlers.map.db.get_dream_map", return_value=_cached(patterns)):
        await cmd_map(update, ctx)

    text = query.edit_message_text.await_args.kwargs["text"]
    assert "вода" in text
    assert "Сейчас снов: 5" in text
    assert "минимум 10" in text


@pytest.mark.asyncio
async def test_cmd_map_handles_corrupt_cache():
    update, query = _callback_update()
    ctx = SimpleNamespace(user_data={})
    cached = _cached()
    cached["patterns_json"] = "не JSON"

    with patch("handlers.map.db.count_dreams", return_value=10), \
         patch("handlers.map.db.get_dream_map", return_value=cached):
        await cmd_map(update, ctx)

    text = query.edit_message_text.await_args.kwargs["text"]
    assert "Не удалось прочитать" in text
    assert query.edit_message_text.await_args.kwargs["reply_markup"] is not None


@pytest.mark.asyncio
async def test_cmd_map_works_as_command():
    update, message = _message_update()
    ctx = SimpleNamespace(user_data={})

    with patch("handlers.map.db.count_dreams", return_value=0), \
         patch("handlers.map.db.get_dream_map", return_value=None):
        await cmd_map(update, ctx)

    message.reply_text.assert_awaited_once()
    assert "минимум 10" in message.reply_text.call_args.kwargs["text"]


@pytest.mark.asyncio
async def test_cmd_map_splits_long_cached_result():
    update, query = _callback_update()
    ctx = SimpleNamespace(user_data={})
    patterns = [
        {
            "pattern": "длинный паттерн",
            "count": 100,
            "examples": ["пример номер один с несколькими словами"] * 150,
            "description": "Описание.",
        }
    ]

    with patch("handlers.map.db.count_dreams", return_value=100), \
         patch(
             "handlers.map.db.get_dream_map",
             return_value=_cached(patterns, dreams_count=100),
         ):
        await cmd_map(update, ctx)

    assert query.message.reply_text.await_count >= 1
    last = query.message.reply_text.await_args_list[-1].kwargs
    assert last["reply_markup"] is not None
