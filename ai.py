import json
import logging
import os
from pathlib import Path

from google import genai
from google.genai import types

import db

log = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"
SUMMARY_PATH = PROMPTS_DIR / "summary.md"
DREAM_MAP_PATH = PROMPTS_DIR / "dream_map.md"

MODEL = "gemini-2.0-flash"

_client = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    return _client


def _call_gemini(system: str, user: str) -> str:
    client = _get_client()
    response = client.models.generate_content(
        model=MODEL,
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system,
        ),
    )
    return response.text


def generate_dream_map(user_id: int) -> list[dict]:
    dreams = db.list_all_dreams(user_id)
    if not dreams:
        return []

    prompt_text = DREAM_MAP_PATH.read_text(encoding="utf-8")
    summary = SUMMARY_PATH.read_text(encoding="utf-8") if SUMMARY_PATH.exists() else ""

    dreams_text = "Сны пользователя:\n\n"
    for i, row in enumerate(dreams, 1):
        dreams_text += (
            f"Сон {i}:\n"
            f"Дата: {row['date']}\n"
            f"Название: {row['title']}\n"
            f"Описание: {row['description']}\n\n"
        )

    user_content = dreams_text
    if summary:
        user_content = "=== База знаний ===\n" + summary + "\n\n" + user_content

    log.info(
        "Запрашиваю карту снов для user_id=%d (%d снов, ~%d символов контекста)",
        user_id,
        len(dreams),
        len(user_content),
    )

    raw = _call_gemini(prompt_text, user_content).strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        log.exception("Невалидный JSON от Gemini: %s", e)
        log.debug("Ответ модели: %s", raw[:500])
        return []

    if not isinstance(data, list):
        log.warning("Ожидался список, получено: %s", type(data))
        return []

    return data
