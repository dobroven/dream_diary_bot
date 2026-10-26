import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from openai import BadRequestError, OpenAI

import db

log = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"
SUMMARY_PATH = PROMPTS_DIR / "summary.md"
DREAM_MAP_PATH = PROMPTS_DIR / "dream_map.md"

BASE_URL = "https://api.zveno.ai/v1"
DREAM_MAP_MODEL = "nvidia/nemotron-3.5-super-vl"

REQUEST_TIMEOUT = 180.0

_client = None


@dataclass
class DreamMapResult:
    patterns: list[dict]
    dreams_count: int
    period_start: str
    period_end: str


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("ZVENOAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("Не задан ZVENOAI_API_KEY")

        # Telegram ходит через PROXY_URL, а ZvenoAI доступен напрямую.
        # Отдельный прокси можно задать через ZVENOAI_PROXY при необходимости.
        proxy = os.environ.get("ZVENOAI_PROXY", "").strip()
        http_client = (
            httpx.Client(proxy=proxy, timeout=httpx.Timeout(REQUEST_TIMEOUT))
            if proxy
            else httpx.Client(timeout=httpx.Timeout(REQUEST_TIMEOUT))
        )
        _client = OpenAI(
            api_key=api_key,
            base_url=BASE_URL,
            http_client=http_client,
            max_retries=1,
        )
    return _client


def _call_llm(system: str, user: str, model: str) -> str:
    client = _get_client()
    log.info("Модель: %s", model)
    kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "timeout": REQUEST_TIMEOUT,
    }

    try:
        response = client.chat.completions.create(
            **kwargs,
            extra_body={"reasoning": {"effort": "low"}},
        )
    except BadRequestError as e:
        # Некоторые провайдеры не принимают reasoning для конкретной модели.
        # В этом случае повторяем запрос без необязательного параметра.
        if "reasoning" not in str(e).lower():
            raise
        log.warning("Провайдер отклонил reasoning, повторяю без него: %s", e)
        response = client.chat.completions.create(**kwargs)

    return response.choices[0].message.content or ""


def _strip_markdown_fences(raw: str) -> str:
    text = raw.strip()
    if not text.startswith("```"):
        return text

    newline = text.find("\n")
    text = text[3:] if newline == -1 else text[newline + 1:]
    text = text.rstrip()
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _parse_patterns(raw: str) -> list[dict[str, Any]]:
    """Достаёт JSON из ответа модели, даже если вокруг есть пояснения."""
    text = _strip_markdown_fences(raw)
    candidates = [text]

    for opener, closer in (("[", "]"), ("{", "}")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end > start:
            candidate = text[start:end + 1]
            if candidate not in candidates:
                candidates.append(candidate)

    data = None
    for candidate in candidates:
        try:
            data = json.loads(candidate)
            break
        except json.JSONDecodeError:
            continue

    if data is None:
        log.error("Модель вернула невалидный JSON")
        log.debug("Ответ модели: %s", text[:500])
        return []

    if isinstance(data, dict):
        data = data.get("patterns", [])

    if not isinstance(data, list):
        log.warning("Ожидался список паттернов, получено: %s", type(data).__name__)
        return []

    return [item for item in data if isinstance(item, dict)]


def validate_dream_map(patterns: list[dict]) -> list[dict]:
    """Страховка от несоблюдения моделью правил count>=2 и длины примеров."""
    result = []
    for p in patterns:
        if not isinstance(p, dict):
            continue

        try:
            count = int(p.get("count", 0))
        except (TypeError, ValueError):
            continue
        if count < 2:
            continue

        examples = []
        raw_examples = p.get("examples", [])
        if isinstance(raw_examples, list):
            for ex in raw_examples:
                if not isinstance(ex, str):
                    continue
                words = ex.split()
                if len(words) > 12:
                    ex = " ".join(words[:10]) + "…"
                examples.append(ex)

        item = dict(p)
        raw_pattern = p.get("pattern")
        item["pattern"] = str(raw_pattern).strip() if raw_pattern else "?"
        item["count"] = count
        item["examples"] = examples
        item["description"] = str(p.get("description") or "").strip()
        result.append(item)

    result.sort(key=lambda p: p["count"], reverse=True)
    return result[:15]


def generate_dream_map(user_id: int, min_dreams: int = 0) -> DreamMapResult:
    dreams = db.list_dreams_for_map(user_id)
    if not dreams or len(dreams) < min_dreams:
        return DreamMapResult([], len(dreams), "", "")

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

    raw = _call_llm(prompt_text, user_content, DREAM_MAP_MODEL).strip()
    patterns = validate_dream_map(_parse_patterns(raw))
    return DreamMapResult(
        patterns=patterns,
        dreams_count=len(dreams),
        period_start=min(row["date"] for row in dreams),
        period_end=max(row["date"] for row in dreams),
    )
