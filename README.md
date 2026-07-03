# 🌙 Dream Diary Bot

Telegram-бот для ведения дневника сновидений. Хранит сны в локальной SQLite-базе, изолируя данные по `user_id`.

## Структура проекта

```
dream_diary/
├── bot.py            # Логика бота (handlers, ConversationHandler)
├── db.py             # Слой базы данных (SQLite)
├── test_db.py        # Тесты для db.py
├── requirements.txt
└── dreams.db         # Создаётся автоматически при первом запуске
```


## Команды бота

| Команда | Описание |
|---|---|
| `/start` | Главное меню с инлайн‑кнопками |
| `/help` | Подробная справка по всем командам |
| `/add` | Записать новый сон (диалог: название → описание) (кнопка "📥 Добавить") |
| `/list` | Список снов с пагинацией (5 за страницу) (кнопка "📄 Список") |
| `/search <слова>` | Поиск по названию и описанию, до 20 результатов (кнопка "🔍 Поиск") |
| `/delete <#N или название>` | Удалить сон по номеру (с учётом текущей страницы) или названию (кнопка "🗑 Удалить") |
| `/cancel` | Отменить текущий ввод |

---

## Кнопки

Бот предлагает **инлайн‑кнопки** в главном меню:

- **🏠 Главная** – вернуть главное меню.
- **📥 Добавить** – начать запись сна.
- **📄 Список** – просмотреть список записей.
- **🔍 Поиск** – ввести запрос для поиска.
- **🗑 Удалить** – ввести номер сна для удаления.

Кнопки дублируют текстовые команды, которые остаются резервным способом управления.

После вызова списка появляются кнопки **«Читать N»**, **«Далее ▶»** / **«◀ Назад»** для пагинации, а после просмотра сна — **«◀️ Назад к списку»**.


## Как выглядит запись

Каждый сон содержит:

- **Название** — строка от 1 до 120 символов
- **Описание** — от 1 до 2000 символов
- **Дата** — автоматически (сегодня)

При попытке сохранить пустой заголовок или описание бот попросит повторить ввод. Превышение лимита длины также блокируется.

---

## Обработка ошибок

- Все операции с базой данных обёрнуты в `try/except sqlite3.Error`. При сбое бот логирует ошибку и возвращает пользователю понятное сообщение (сон не сохранён / не найден / удалён).
- Удаление по номеру корректно работает на любой странице списка: бот запоминает текущее смещение (`offset`) и вычисляет индекс в рамках страницы.
- Поиск ограничен 20 результатами; если их ровно 20, пользователь видит подсказку уточнить запрос.

---

## База данных

Файл `dreams.db` создаётся рядом с `bot.py`. Структура таблицы:

```sql
CREATE TABLE dreams (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,   -- Telegram user ID
    date        TEXT    NOT NULL,   -- YYYY-MM-DD
    title       TEXT    NOT NULL,
    description TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_dreams_user_date ON dreams (user_id, date DESC);
```

Каждый пользователь видит только свои сны — изоляция по `user_id`.

Для корректного поиска по кириллице используется `str.casefold()` на стороне Python (SQLite `LOWER` не обрабатывает не-ASCII символы).

---

## Тесты

```bash
.venv/bin/python -m pytest test_db.py -v
```

Перед запуском установите `pytest` и `pytest-asyncio`:

```bash
.venv/bin/pip install pytest pytest-asyncio
```

---

## Деплой (опционально)

### Systemd (Linux VPS)

```ini
# /etc/systemd/system/dreambot.service
[Unit]
Description=Dream Diary Telegram Bot
After=network.target

[Service]
WorkingDirectory=/opt/dream_diary
Environment=TELEGRAM_BOT_TOKEN=ваш_токен
ExecStart=/opt/dream_diary/.venv/bin/python bot.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable dreambot
systemctl start dreambot
```

### Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "bot.py"]
```
