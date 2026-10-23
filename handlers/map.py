import asyncio
import logging

from openai import APIStatusError, RateLimitError
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

import ai
import db
from utils import BOOK, _esc

log = logging.getLogger(__name__)

MODEL_LABEL = "🧠 Nemotron 3.5 Super VL"

MAIN_MENU = InlineKeyboardMarkup(
    [[InlineKeyboardButton("🏠 Главная", callback_data="menu:main")]]
)


def _split_text(text: str, limit: int = 4096) -> list[str]:
    """Делит длинный текст на части, не разрывая строки без необходимости."""
    parts = []
    while len(text) > limit:
        idx = text.rfind("\n", 0, limit)
        if idx <= 0:
            idx = text.rfind(" ", 0, limit)
        if idx <= 0:
            idx = limit
        parts.append(text[:idx])
        text = text[idx:].lstrip("\n ")
    parts.append(text)
    return parts


async def _replace(update: Update, text: str, markup=None) -> None:
    """Заменяет сообщение меню (callback) или отправляет новое (команда)."""
    kwargs = {"text": text, "parse_mode": ParseMode.MARKDOWN_V2}
    if markup is not None:
        kwargs["reply_markup"] = markup

    if update.callback_query:
        await update.callback_query.edit_message_text(**kwargs)
    else:
        await update.message.reply_text(**kwargs)


async def _follow(update: Update, text: str, markup=None) -> None:
    kwargs = {"text": text, "parse_mode": ParseMode.MARKDOWN_V2}
    if markup is not None:
        kwargs["reply_markup"] = markup

    if update.callback_query:
        await update.callback_query.message.reply_text(**kwargs)
    else:
        await update.message.reply_text(**kwargs)


async def _send_result(update: Update, text: str) -> None:
    parts = _split_text(text)
    for i, part in enumerate(parts):
        markup = MAIN_MENU if i == len(parts) - 1 else None
        if i == 0:
            await _replace(update, part, markup)
        else:
            await _follow(update, part, markup)


async def cmd_map(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    total = db.count_dreams(user_id)

    if total == 0:
        await _replace(
            update,
            _esc(f"{BOOK} Сначала запиши хотя бы один сон через кнопку «Добавить»."),
            MAIN_MENU,
        )
        return

    try:
        await _replace(
            update,
            _esc(
                f"🗺 {MODEL_LABEL} — составляю карту твоих снов… "
                "Это может занять до двух минут."
            ),
        )
    except BadRequest:
        # Повторное нажатие на кнопку: сообщение уже содержит этот статус.
        pass

    try:
        patterns, analyzed = await asyncio.to_thread(ai.generate_dream_map, user_id)
    except RateLimitError as e:
        log.warning("ZvenoAI ограничил запросы при генерации карты снов: %s", e)
        await _replace(
            update,
            _esc(
                "⏳ ZvenoAI временно ограничил запросы. Попробуй позже."
            ),
            MAIN_MENU,
        )
        return
    except APIStatusError as e:
        if e.status_code == 402:
            log.warning("Недостаточно средств на балансе ZvenoAI: %s", e)
            await _replace(
                update,
                _esc(
                    "💳 Недостаточно средств на балансе ZvenoAI. "
                    "Пополни баланс и попробуй снова."
                ),
                MAIN_MENU,
            )
            return
        log.exception("Ошибка API ZvenoAI при генерации карты снов: %s", e)
        await _replace(
            update,
            _esc("❌ Сервис ZvenoAI вернул ошибку. Попробуй позже."),
            MAIN_MENU,
        )
        return
    except Exception as e:
        log.exception("Ошибка при генерации карты снов: %s", e)
        await _replace(
            update,
            _esc("❌ Произошла ошибка при составлении карты. Попробуй позже."),
            MAIN_MENU,
        )
        return

    if not patterns:
        await _replace(
            update,
            _esc(
                "🗺 Повторяющихся паттернов не найдено. "
                "Добавь ещё снов и попробуй снова."
            ),
            MAIN_MENU,
        )
        return

    lines = [
        f"🗺 *Карта сновидений* \\({_esc(MODEL_LABEL)}\\)",
        f"Всего снов: {total} · в анализ вошло: {analyzed}",
        "",
    ]
    for p in patterns:
        pattern = p.get("pattern", "?")
        count = p.get("count", 0)
        desc = p.get("description", "")
        examples = p.get("examples", [])

        lines.append(f"🔁 *{_esc(str(pattern))}* — {count} сн\\.")
        if desc:
            lines.append(_esc(str(desc)))
        for ex in examples:
            lines.append(f"▸ {_esc(str(ex))}")
        lines.append("")

    await _send_result(update, "\n".join(lines))
