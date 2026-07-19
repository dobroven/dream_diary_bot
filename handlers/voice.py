import asyncio
import logging
import os
import tempfile
from textwrap import shorten

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import db
from utils import _esc, MOON, STAR, VOICE

log = logging.getLogger(__name__)

_model = None


def get_model():
    global _model
    if _model is None:
        log.info("Loading faster-whisper model 'base'...")
        from faster_whisper import WhisperModel
        _model = WhisperModel("base", device="cpu", compute_type="int8")
        log.info("Whisper model loaded")
    return _model


def _generate_title(text: str, max_len: int = 120) -> str:
    text = text.strip()
    if not text:
        return "Голосовой сон"

    for sep in ('.', '!', '?', '\n'):
        idx = text.find(sep)
        if idx != -1 and idx + 1 <= max_len:
            candidate = text[:idx + 1].strip()
            if candidate:
                return candidate

    if len(text) <= max_len:
        return text

    truncated = text[:max_len]
    last_space = truncated.rfind(' ')
    if last_space > 0:
        truncated = truncated[:last_space] + '…'
    else:
        truncated = truncated + '…'
    return truncated


def _transcribe(filepath: str) -> str:
    model = get_model()
    segments, _info = model.transcribe(filepath, beam_size=5, language="ru")
    return " ".join(seg.text for seg in segments).strip()


async def handle_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    voice = update.message.voice

    if voice.duration > 300:
        await update.message.reply_text(
            _esc("⚠️ Голосовое сообщение слишком длинное (макс. 5 минут).")
        )
        return

    status_msg = await update.message.reply_text(f"{VOICE} {_esc('Распознаю речь...')}")

    file = await voice.get_file()

    tmp = tempfile.NamedTemporaryFile(suffix=".ogg", delete=False)
    tmp_path = tmp.name
    tmp.close()

    try:
        await file.download_to_drive(tmp_path)

        loop = asyncio.get_event_loop()
        transcription = await loop.run_in_executor(None, _transcribe, tmp_path)

        if not transcription:
            await status_msg.edit_text(_esc("⚠️ Не удалось распознать речь. Попробуй ещё раз."))
            return

        title = _generate_title(transcription)
        description = transcription[:2000]

        if len(title) > 120:
            title = title[:117] + '…'

        user_id = update.effective_user.id
        dream_id = await asyncio.to_thread(db.add_dream, user_id, title, description)

        if dream_id is None:
            await status_msg.edit_text(_esc("❌ Произошла ошибка при сохранении. Попробуй ещё раз."))
            return

        preview = shorten(description, 200, placeholder='…')

        await status_msg.edit_text(
            f"{STAR} {_esc('Сон сохранён!')}\n\n"
            f"{MOON} *{_esc(title)}*\n"
            f"{_esc(preview)}",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Главная", callback_data="menu:main")]
            ]),
        )

    except Exception:
        log.exception("Ошибка при обработке голосового сообщения")
        await status_msg.edit_text(_esc("❌ Произошла ошибка при обработке голосового сообщения."))
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
