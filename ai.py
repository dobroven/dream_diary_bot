import json
import logging
import os
from pathlib import Path

from openai import OpenAI

import db

log = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"
SUMMARY_PATH = PROMPTS_DIR / "summary.md"
DREAM_MAP_PATH = PROMPTS_DIR / "dream_map.md"

BASE_URL = "https://api.groq.com/openai/v1"
MODEL = "mixtral-8x7b-32768"

_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.environ.get("GROQ_API_KEY"),
            base_url=BASE_URL,
        )
    return _client


def _call_deepseek(system: str, user: str) -> str:
    client = _get_client()
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return response.choices[0].message.content or ""


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

    raw = _call_deepseek(prompt_text, user_content).strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        log.exception("Невалидный JSON от DeepSeek: %s", e)
        log.debug("Ответ модели: %s", raw[:500])
        return []

    if not isinstance(data, list):
        log.warning("Ожидался список, получено: %s", type(data))
        return []

    return data
