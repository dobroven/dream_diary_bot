import asyncio
import logging
from contextlib import suppress

from openai import APIStatusError, RateLimitError
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import Application

import ai
import db
from utils import (
    MAP_REFRESH_DAYS,
    MIN_DREAMS_FOR_MAP,
    _esc,
    format_date,
)

log = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 6 * 60 * 60
STARTUP_DELAY_SECONDS = 10

MAP_BUTTON = InlineKeyboardMarkup(
    [[InlineKeyboardButton("🗺 Посмотреть карту", callback_data="menu:map")]]
)


async def _notify(bot, user_id: int, result: ai.DreamMapResult) -> None:
    period_start = format_date(result.period_start)
    period_end = format_date(result.period_end)
    period = f"{period_start} — {period_end}" if period_start and period_end else "—"
    text = (
        "🗺 *Карта снов обновлена*\n"
        f"Период: {_esc(period)}\n"
        "Нажми кнопку, чтобы посмотреть."
    )

    try:
        await bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=MAP_BUTTON,
        )
    except TelegramError as e:
        log.warning("Не удалось отправить уведомление о карте user_id=%s: %s", user_id, e)


async def refresh_due_maps(bot=None) -> list[int]:
    """Генерирует и сохраняет карты для пользователей, которым пора обновиться."""
    generated = []
    user_ids = db.list_users_due_for_map(
        interval_days=MAP_REFRESH_DAYS,
        min_dreams=MIN_DREAMS_FOR_MAP,
    )

    for user_id in user_ids:
        if db.count_dreams(user_id) < MIN_DREAMS_FOR_MAP:
            log.info("Карта снов: у user_id=%s меньше %d снов, пропускаю", user_id, MIN_DREAMS_FOR_MAP)
            continue

        try:
            result = await asyncio.to_thread(
                ai.generate_dream_map, user_id, MIN_DREAMS_FOR_MAP
            )
        except RateLimitError as e:
            log.warning("Карта снов: ZvenoAI ограничил запросы для user_id=%s: %s", user_id, e)
            continue
        except APIStatusError as e:
            if e.status_code == 402:
                log.warning("Карта снов: недостаточно средств ZvenoAI для user_id=%s: %s", user_id, e)
            else:
                log.exception("Карта снов: ошибка API ZvenoAI для user_id=%s: %s", user_id, e)
            continue
        except Exception as e:
            log.exception("Карта снов: ошибка генерации для user_id=%s: %s", user_id, e)
            continue

        if result.dreams_count < MIN_DREAMS_FOR_MAP:
            log.warning(
                "Карта снов: для user_id=%s в анализ попало %d снов, нужно минимум %d",
                user_id,
                result.dreams_count,
                MIN_DREAMS_FOR_MAP,
            )
            continue

        saved = db.save_dream_map(
            user_id=user_id,
            patterns=result.patterns,
            dreams_count=result.dreams_count,
            period_start=result.period_start,
            period_end=result.period_end,
        )
        if not saved:
            continue

        generated.append(user_id)
        if bot is not None:
            await _notify(bot, user_id, result)

    return generated


async def map_refresh_loop(bot) -> None:
    await asyncio.sleep(STARTUP_DELAY_SECONDS)
    while True:
        try:
            await refresh_due_maps(bot)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Карта снов: ошибка в фоновом планировщике")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


async def start_map_scheduler(app: Application) -> None:
    task = asyncio.create_task(map_refresh_loop(app.bot), name="map-refresh")
    app.bot_data["map_refresh_task"] = task
    log.info("Планировщик карты снов запущен")


async def stop_map_scheduler(app: Application) -> None:
    task = app.bot_data.pop("map_refresh_task", None)
    if task is None:
        return
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
    log.info("Планировщик карты снов остановлен")
