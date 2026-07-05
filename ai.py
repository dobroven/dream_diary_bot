import json
import logging
import os
from pathlib import Path

from openai import OpenAI

import db

log = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"
BOOKS_DIR = PROMPTS_DIR / "books"
COMPILED_PATH = PROMPTS_DIR / "compiled_books.md"
DREAM_MAP_PATH = PROMPTS_DIR / "dream_map.md"

BASE_URL = "https://openrouter.ai/api/v1"
MODEL = "deepseek/deepseek-chat"

_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.environ.get("OPENROUTER_API_KEY"),
            base_url=BASE_URL,
        )
    return _client


def _call_openrouter(system: str, user: str) -> str:
    client = _get_client()
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return response.choices[0].message.content or ""


def extract_docx_text(path: str | Path) -> str:
    from docx import Document

    doc = Document(str(path))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


def compile_books() -> str:
    docx_files = list(BOOKS_DIR.glob("*.docx"))
    if not docx_files:
        log.warning("Нет книг в %s", BOOKS_DIR)
        return ""

    book_texts = []
    for fp in docx_files:
        log.info("Читаю книгу: %s", fp.name)
        text = extract_docx_text(fp)
        book_texts.append(f"=== {fp.name} ===\n{text}")

    full_text = "\n\n".join(book_texts)

    system_prompt = """Ты — специалист по анализу сновидений. Извлеки из книги ключевые концепции, техники анализа, особенности и методы поиска паттернов сновидений. Скомпилируй в краткий структурированный конспект. Конспект будет использован как база знаний для поиска повторяющихся признаков в дневнике снов пользователя. Формат: Markdown, русский язык."""

    log.info("Отправляю книгу на компиляцию (%d символов)", len(full_text))
    result = _call_openrouter(system_prompt, full_text)
    COMPILED_PATH.write_text(result, encoding="utf-8")
    log.info("Скомпилировано в %s (%d символов)", COMPILED_PATH, len(result))
    return result


def get_or_compile_books() -> str:
    if COMPILED_PATH.exists():
        return COMPILED_PATH.read_text(encoding="utf-8")
    return compile_books()


def generate_dream_map(user_id: int) -> list[dict]:
    dreams = db.list_all_dreams(user_id)
    if not dreams:
        return []

    compiled = get_or_compile_books()
    prompt_text = DREAM_MAP_PATH.read_text(encoding="utf-8")

    dreams_text = "Сны пользователя:\n\n"
    for i, row in enumerate(dreams, 1):
        dreams_text += (
            f"Сон {i}:\n"
            f"Дата: {row['date']}\n"
            f"Название: {row['title']}\n"
            f"Описание: {row['description']}\n\n"
        )

    user_content = dreams_text
    if compiled:
        user_content = "=== База знаний ===\n" + compiled + "\n\n" + user_content

    log.info(
        "Запрашиваю карту снов для user_id=%d (%d снов, ~%d символов контекста)",
        user_id,
        len(dreams),
        len(user_content),
    )

    raw = _call_openrouter(prompt_text, user_content)

    raw = raw.strip()
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
