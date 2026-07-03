import json
import logging
import os
from pathlib import Path

from google import genai as genai_client

import db

log = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"
BOOKS_DIR = PROMPTS_DIR / "books"
COMPILED_PATH = PROMPTS_DIR / "compiled_books.md"
DREAM_MAP_PATH = PROMPTS_DIR / "dream_map.md"

COMPILE_PROMPT = """Ты — специалист по анализу сновидений. Прочитай приложенную книгу и извлеки из неё:

1. **Концепции** — ключевые идеи о природе и структуре сновидений
2. **Техники** — методы анализа и интерпретации снов
3. **Особенности** — важные нюансы, которые нужно учитывать при разборе снов
4. **Методы поиска паттернов** — как выявлять повторяющиеся элементы, символы, сюжеты

Скомпилируй в краткий структурированный конспект.
Конспект будет использован как база знаний для поиска повторяющихся признаков в дневнике снов пользователя.

Формат: Markdown, русский язык."""

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai_client.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    return _client


def _call_gemini(contents: list[str]) -> str:
    client = _get_client()
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=contents,
    )
    return response.text


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

    log.info("Отправляю книгу на компиляцию (%d символов)", len(full_text))
    result = _call_gemini([COMPILE_PROMPT, full_text]).strip()
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

    contents = [prompt_text]
    if compiled:
        contents.append("=== База знаний ===\n" + compiled)
    contents.append(dreams_text)

    log.info(
        "Запрашиваю карту снов для user_id=%d (%d снов, ~%d символов контекста)",
        user_id,
        len(dreams),
        sum(len(c) for c in contents),
    )

    raw = _call_gemini(contents).strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        log.exception("Невалидный JSON от Gemini: %s", e)
        log.debug("Ответ Gemini: %s", raw[:500])
        return []

    if not isinstance(data, list):
        log.warning("Ожидался список, получено: %s", type(data))
        return []

    return data
