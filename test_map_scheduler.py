import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from openai import APIStatusError, RateLimitError
from telegram.error import TelegramError

import ai
import map_scheduler


def _result(dreams_count=14):
    return ai.DreamMapResult(
        patterns=[{"pattern": "полёт", "count": 2, "examples": ["летал"]}],
        dreams_count=dreams_count,
        period_start="2026-09-27",
        period_end="2026-10-19",
    )


def _api_error(status_code: int) -> APIStatusError:
    request = httpx.Request("POST", "https://api.zveno.ai/v1/chat/completions")
    response = httpx.Response(status_code, request=request)
    return APIStatusError("api error", response=response, body=None)


def _rate_limit_error() -> RateLimitError:
    request = httpx.Request("POST", "https://api.zveno.ai/v1/chat/completions")
    response = httpx.Response(429, request=request)
    return RateLimitError("rate limit", response=response, body=None)


@pytest.mark.asyncio
async def test_refresh_due_maps_generates_saves_and_notifies():
    bot = SimpleNamespace(send_message=AsyncMock())
    result = _result()

    with patch("map_scheduler.db.list_users_due_for_map", return_value=[1]) as due, \
         patch("map_scheduler.db.count_dreams", return_value=20), \
         patch("map_scheduler.ai.generate_dream_map", return_value=result) as generate, \
         patch("map_scheduler.db.save_dream_map", return_value=True) as save:
        generated = await map_scheduler.refresh_due_maps(bot)

    assert generated == [1]
    due.assert_called_once_with(interval_days=14, min_dreams=10, min_new_dreams=7)
    generate.assert_called_once_with(1, 10)
    save.assert_called_once_with(
        user_id=1,
        patterns=result.patterns,
        dreams_count=14,
        period_start="2026-09-27",
        period_end="2026-10-19",
    )

    bot.send_message.assert_awaited_once()
    message = bot.send_message.await_args.kwargs
    assert message["chat_id"] == 1
    assert "Карта снов обновлена" in message["text"]
    assert "27\\.09\\.2026 — 19\\.10\\.2026" in message["text"]
    assert message["reply_markup"] is not None


@pytest.mark.asyncio
async def test_refresh_due_maps_skips_user_with_less_than_ten_dreams():
    bot = SimpleNamespace(send_message=AsyncMock())

    with patch("map_scheduler.db.list_users_due_for_map", return_value=[1]), \
         patch("map_scheduler.db.count_dreams", return_value=9), \
         patch("map_scheduler.ai.generate_dream_map") as generate, \
         patch("map_scheduler.db.save_dream_map") as save:
        generated = await map_scheduler.refresh_due_maps(bot)

    assert generated == []
    generate.assert_not_called()
    save.assert_not_called()
    bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_due_maps_skips_result_with_too_few_dreams():
    bot = SimpleNamespace(send_message=AsyncMock())

    with patch("map_scheduler.db.list_users_due_for_map", return_value=[1]), \
         patch("map_scheduler.db.count_dreams", return_value=20), \
         patch("map_scheduler.ai.generate_dream_map", return_value=_result(9)), \
         patch("map_scheduler.db.save_dream_map") as save:
        generated = await map_scheduler.refresh_due_maps(bot)

    assert generated == []
    save.assert_not_called()
    bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_due_maps_keeps_cache_on_api_error():
    bot = SimpleNamespace(send_message=AsyncMock())

    with patch("map_scheduler.db.list_users_due_for_map", return_value=[1]), \
         patch("map_scheduler.db.count_dreams", return_value=20), \
         patch("map_scheduler.ai.generate_dream_map", side_effect=_api_error(500)), \
         patch("map_scheduler.db.save_dream_map") as save:
        generated = await map_scheduler.refresh_due_maps(bot)

    assert generated == []
    save.assert_not_called()
    bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_due_maps_keeps_cache_on_rate_limit():
    bot = SimpleNamespace(send_message=AsyncMock())

    with patch("map_scheduler.db.list_users_due_for_map", return_value=[1]), \
         patch("map_scheduler.db.count_dreams", return_value=20), \
         patch("map_scheduler.ai.generate_dream_map", side_effect=_rate_limit_error()), \
         patch("map_scheduler.db.save_dream_map") as save:
        generated = await map_scheduler.refresh_due_maps(bot)

    assert generated == []
    save.assert_not_called()
    bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_due_maps_does_not_notify_if_save_fails():
    bot = SimpleNamespace(send_message=AsyncMock())

    with patch("map_scheduler.db.list_users_due_for_map", return_value=[1]), \
         patch("map_scheduler.db.count_dreams", return_value=20), \
         patch("map_scheduler.ai.generate_dream_map", return_value=_result()), \
         patch("map_scheduler.db.save_dream_map", return_value=False):
        generated = await map_scheduler.refresh_due_maps(bot)

    assert generated == []
    bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_due_maps_ignores_notification_error():
    bot = SimpleNamespace(send_message=AsyncMock(side_effect=TelegramError("closed")))

    with patch("map_scheduler.db.list_users_due_for_map", return_value=[1]), \
         patch("map_scheduler.db.count_dreams", return_value=20), \
         patch("map_scheduler.ai.generate_dream_map", return_value=_result()), \
         patch("map_scheduler.db.save_dream_map", return_value=True):
        generated = await map_scheduler.refresh_due_maps(bot)

    assert generated == [1]
    bot.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_and_stop_scheduler():
    app = SimpleNamespace(bot=MagicMock(), bot_data={})
    blocking = asyncio.Event()

    async def fake_loop(bot):
        await blocking.wait()

    with patch("map_scheduler.map_refresh_loop", side_effect=fake_loop):
        await map_scheduler.start_map_scheduler(app)
        task = app.bot_data["map_refresh_task"]
        assert not task.done()

        await map_scheduler.stop_map_scheduler(app)

    assert "map_refresh_task" not in app.bot_data
    assert task.cancelled()
