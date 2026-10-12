# Day 27 — Интеграция локальной LLM в Telegram-бота

## Цель

Интегрировать **локальную** LLM (`gemma4:12b` через Ollama) в реальное приложение —
**Telegram-бота**. Бот принимает сообщения и фотографии, обращается к локальной модели,
отображает ответ (в т.ч. стримингом) и работает **без облачных моделей**. Итог — Telegram-бот
с полным набором функций (память диалога, стриминг, команды, vision), в стиле остальных дней
проекта: код + `README.md`, `LESSON.md`, `lesson.html`, `video-script.html`.

Формат задания: **Видео + Код**.

## Контекст

- День 26 поднял локальную LLM: Ollama + `gemma4:12b` (11.9B, Q4_K_M), HTTP API
  `http://localhost:11434`, чат-страница. День 27 делает следующий шаг — **реальное
  приложение**, куда встроена та же локальная модель.
- Паттерн проекта: каждый день = папка `dayN/` с приложением и документами; бэкенд в стиле
  clean architecture (`domain` / `ports` / `infrastructure` / `application` / `presentation`);
  тесты на pytest; спеки — в `docs/superpowers/specs/`.
- Telegram-бот выбран потому, что работает через **long polling** — не нужен публичный
  URL/вебхук, поэтому локальная модель на домашнем ПК сочетается с Telegram напрямую.

## Вне-цели (YAGNI)

- Без групповых чатов (только личка). Заложены в дизайн как возможное расширение, но не
  реализуются.
- Без вебхуков и деплоя в облако. Только long polling на localhost.
- Без RAG/инструментов/MCP — задача про интеграцию локальной модели, а не про агентов.
- Без inline-режима, клавиатур-меню, платежей и т.п.
- Без потокового ASR/TTS и без генерации изображений.
- Без поддержки нескольких одновременных генераций в одном чате (последовательная очередь
  через `asyncio.Lock` — при занятости бот просит подождать).

## Ключевая идея

Ядро не знает ни про Telegram, ни про HTTP к Ollama. Всё общение с моделью — за интерфейсом
`LLMClient`, всё отображение — за интерфейсом-приёмником («presenter»). Это даёт чистые
границы, тестируемость офлайн и возможность заменить Ollama или транспорт без правки логики.

```
Telegram  ⇄  aiogram (presentation)  ⇄  ChatService (application)  ⇄  LLMClient (port)  ⇄  OllamaClient
                        │                        │
                 TelegramStreamer          JsonChatStore
                 (правки/сплит)            (история диалога)
```

### Диаграмма потоков

```
текст:  update → handler → ChatService.ask(chat, text)
                              │  собирает messages = [system] + history + user
                              │  LLMClient.stream_chat(...)  (NDJSON)
                              │    ├─ event.thinking → статус «💭 думает…»
                              │    └─ event.content  → TelegramStreamer.push() (троттлинг edit_text)
                              │  event.done → stats (tok/s) → футер
                              ├─ history.append(user, assistant) → JsonChatStore.save()
                              └─ presenter.finish()

фото:   update(photo) → скачать max-размер → base64
                              │  в историю пишется плейсхолдер "[фото]" (не байты)
                              └─ stream_chat(..., images=[b64], prompt=caption|"Опиши изображение")

команда: router перехватывает до ChatService; /reset, /model, /think меняют состояние.
```

## Архитектура

### Дерево `day27/`

```
day27/
  README.md                       # что это, запуск, команды
  LESSON.md                       # конспект урока
  lesson.html                     # подробный урок «сделай сам» (браузер)
  video-script.html               # сценарий видео (сухое, только действия)
  backend/
    pyproject.toml
    requirements.txt
    .env.example                  # TELEGRAM_BOT_TOKEN, OLLAMA_*, ...
    .gitignore                    # .venv/, __pycache__/, .pytest_cache/, .env, data/
    app/
      __init__.py
      main.py                     # точка входа: config → bot → dispatcher → start_polling
      config.py                   # Settings (pydantic-settings)
      domain/
        __init__.py
        models.py                 # Role, ChatMessage, GenerationStats, ChatState, PhotoInput
      ports/
        __init__.py
        llm.py                    # LLMClient Protocol + события стрима
      infrastructure/
        __init__.py
        ollama_client.py          # OllamaClient: stream_chat / list_models / health (httpx async)
        chat_store.py             # JsonChatStore: load/save/list (data/chats/<id>.json)
      application/
        __init__.py
        chat_service.py           # оркестрация: история, запрос, статистика, обрезка
        formatter.py              # markdown→Telegram HTML, split 4096, футер
      presentation/
        __init__.py
        handlers.py               # aiogram Router: команды, текст, фото
        streamer.py               # TelegramMessageStreamer (throttle edit_text, typing, split)
        middlewares.py            # error middleware, typing action
    tests/
      __init__.py
      conftest.py                 # фикстуры: FakeLLMClient, MockTransport, tmp store
      test_ollama_client.py
      test_chat_service.py
      test_formatter.py
      test_streamer.py
      test_vision.py
docs/superpowers/specs/2026-10-12-day27-telegram-local-llm-design.md   # этот документ
```

### `domain/models.py`

- `Role` — `Enum`: `system | user | assistant`.
- `ChatMessage(role: Role, content: str, images: list[str] | None = None)` — одно сообщение;
  `images` — base64 (используется только в исходящем vision-запросе, в истории хранится
  плейсхолдер).
- `GenerationStats(model, prompt_tokens, completion_tokens, eval_duration_ns, total_duration_ns)`
  с property `tokens_per_second` (completion_tokens / секунды; 0 при отсутствии).
- `ChatState(chat_id: int, messages: list[ChatMessage], system_prompt: str, model: str,
  show_thinking: bool, updated_at: str)`; методы `to_dict()` / `from_dict()`.
- `PhotoInput(data: bytes, mime: str, caption: str | None)`.

### `ports/llm.py`

- Типы событий стрима (dataclass-и или `dataclass` с `kind`):
  - `StreamDelta(kind="thinking"|"content", text: str)`
  - `StreamDone(stats: GenerationStats)`
- `class LLMClient(Protocol)`:
  - `async def stream_chat(self, messages: list[ChatMessage], model: str,
    options: dict | None = None) -> AsyncIterator[StreamDelta | StreamDone]`
  - `async def list_models(self) -> list[ModelInfo]`
  - `async def health(self) -> bool`

### `infrastructure/ollama_client.py`

- `OllamaClient(base_url, timeout, keep_alive, default_options)` — держит один
  `httpx.AsyncClient` (лениво), `aclose()`.
- `stream_chat`: POST `/api/chat` c `stream: true`; парсит NDJSON построчно
  (`message.thinking` → `StreamDelta("thinking")`, `message.content` → `StreamDelta("content")`,
  при `done: true` формирует `GenerationStats` из `eval_count`/`eval_duration`/`prompt_eval_count`).
- `list_models`: GET `/api/tags` → список `name` + `details.parameter_size` (+ capability, если есть).
- `health`: GET `/api/version`, `True` при 200.
- Ошибки: сетевые/статусные → исключение `OllamaUnavailable` (доменное/слоевое исключение),
  которое `ChatService`/middleware превращает в дружелюбное сообщение.

### `infrastructure/chat_store.py`

- `JsonChatStore(root: Path)`:
  - `load(chat_id) -> ChatState | None`
  - `save(state) -> None` (атомарно: временный файл + `os.replace`)
  - `delete(chat_id) -> None`
  - `list_ids() -> list[int]`
- Файлы: `day27/backend/data/chats/<chat_id>.json` (папка gitignored).

### `application/chat_service.py`

- `ChatService(store, llm, settings)`:
  - `get_state(chat_id) -> ChatState` — грузит с диска или создаёт новый (system_prompt,
    model из настроек).
  - `async def stream(state, user_message, images=None) -> AsyncIterator[event]` —
    добавляет ход, строит `messages = [system] + trimmed(history) + user`, отдаёт события
    вверх, по завершении пишет историю (user + assistant-текст; для фото в историю идёт
    плейсхолдер) и сохраняет на диск.
  - `trim(messages)` — оставляет системный промпт + последние `HISTORY_MAX_MESSAGES`
    сообщений, дополнительно обрезает по суммарному `HISTORY_MAX_CHARS`.
  - `reset(chat_id)` — очищает историю (системный промпт сохраняется).
  - `set_model(state, name)` — валидирует по `llm.list_models()`.
  - `set_thinking(state, on: bool)`.
  - `stats(state) -> str` — текст для `/stats`.
- Логика не знает про aiogram и про httpx — принимает `LLMClient` и `JsonChatStore`.

### `application/formatter.py`

- `md_to_telegram_html(text: str) -> str` — экранирует `<`, `>`, `&`; превращает
  ``` ```code``` ``` → `<pre><code>`, `` `code` `` → `<code>`, `**bold**` → `<b>`;
  строки — в абзацы/`<br>`. Никакой небезопасной вставки.
- `split_message(text: str, limit: int = 4096) -> list[str]` — режет по границам строк/слов
  (не внутри слова), чтобы каждый кусок был ≤ `limit`. HTML-теги на границе балансируются:
  незакрытые теги чанка закрываются в его конце и заново открываются в начале следующего,
  поэтому каждый чанк — самостоятельный валидный HTML.
- `footer(stats: GenerationStats | None, model: str) -> str` — `🤖 <model> · локально ·
  ⚡ N tok/s` (или без tok/s, если статистики нет).

### `presentation/streamer.py`

- `TelegramMessageStreamer(send, edit, min_interval=1.2)` — параметризован функциями
  отправки/правки, поэтому тестируется без реального Telegram.
  - `async def start()` — отправляет первое сообщение (статус «💭 думает…»).
  - `async def push(text: str)` — копит; если прошло `min_interval` и текст изменился —
    `edit`. Устойчив к ошибке «message is not modified» и к 429 (ретрай/пропуск тика).
  - `async def finish(final_text, stats, ...)` — финальный flush, разбивка по 4096 в несколько
    сообщений, футер в последнем.
  - При превышении лимита — «переливает» хвост в новое сообщение.
- Конкретная интеграция с aiogram (`sent = await msg.answer(...)`, `sent.edit_text(...)`,
  `ChatActionSender.typing(...)`) — в `handlers.py`, который передаёт в streamer нужные
  callable-ы.

### `presentation/handlers.py`

- `Router` с хендлерами:
  - команды: `/start`, `/help`, `/new` (+`/reset`), `/id`, `/model`, `/stats`, `/think`.
  - `F.photo` → vision-путь.
  - `F.text` → обычный путь (после команд).
- `/start` — баннер: «Я работаю **локально** на твоём компьютере через Ollama (`gemma4:12b`),
  без облака» + список команд.
- `/model` без аргумента — показывает текущую и доступные; `/model <name>` — валидирует и меняет.
- `/think on|off` — включает показ «💭 Размышления» отдельным сообщением.
- Per-chat `asyncio.Lock`: при занятости — «⏳ Я ещё отвечаю на предыдущее сообщение, подожди.»
- Типовая ошибка `OllamaUnavailable` → «⚠️ Локальная модель не отвечает. Запусти `ollama serve`.»

### `presentation/middlewares.py`

- Middleware обработки ошибок: ловит исключения, логирует, шлёт пользователю аккуратный текст;
  не роняет polling.
- (Опционально) middleware, который включает `ChatActionSender.typing` на время обработки.

### `config.py`

`Settings(BaseSettings)` (env + `.env`):

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — (обязательно) | токен бота |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | адрес Ollama |
| `OLLAMA_MODEL` | `gemma4:12b` | модель |
| `OLLAMA_NUM_CTX` | `8192` | размер контекста |
| `OLLAMA_KEEP_ALIVE` | `10m` | сколько держать модель в RAM/VRAM |
| `SYSTEM_PROMPT` | краткая инструкция | системный промпт |
| `HISTORY_MAX_MESSAGES` | `20` | глубина истории |
| `HISTORY_MAX_CHARS` | `12000` | лимит объёма истории |
| `REQUEST_TIMEOUT` | `300` | HTTP-таймаут к Ollama |

### `main.py`

- Читает `Settings`, собирает `OllamaClient`, `JsonChatStore`, `ChatService`, `Bot`,
  `Dispatcher`, включает роутер и middleware, `asyncio.run(dp.start_polling(bot))`.
- При старте: `llm.health()` → лог «Ollama: OK / недоступна», список моделей, активная модель.

## Модель данных

`data/chats/<chat_id>.json`:

```json
{
  "chat_id": 42,
  "system_prompt": "Ты — полезный ассистент...",
  "model": "gemma4:12b",
  "show_thinking": false,
  "updated_at": "2026-10-12T10:00:00Z",
  "messages": [
    {"role": "user", "content": "Привет! Кто ты?"},
    {"role": "assistant", "content": "Я локальная модель gemma4:12b..."},
    {"role": "user", "content": "[фото]"}
  ]
}
```

## Обработка ошибок и краевые случаи

- **Ollama недоступна/таймаут** → `OllamaUnavailable` → дружелюбное сообщение, polling живёт.
- **Ответ > 4096** → `split_message` + отправка несколькими сообщениями, футер в последнем.
- **Telegram 429 / «not modified»** → `edit_text` в try/except, ретрай с backoff, пропуск
  идентичной правки.
- **Параллельные сообщения в одном чате** → `asyncio.Lock`, ответ «подожди». Разные чаты —
  конкурентно (один общий `AsyncClient`, Ollama сам ставит в очередь).
- **Очень длинное «размышление»** → тайп-индикатор и статус «💭 думает…» всё время; таймаут 300 с.
- **Некорректные HTML-entities после конвертации** → фолбэк на отправку простым текстом.
- **Фото без подписи** → дефолтный промпт «Опиши изображение».
- **История разрослась** → `trim` по числу сообщений и по символам.
- **Нет токена в `.env`** → понятная ошибка на старте, процесс завершается.
- **Модель не найдена в `/api/tags`** при `/model` → сообщение со списком доступных.

## Тесты (офлайн, детерминированно) — ориентир ≥15

- `test_ollama_client.py` (`httpx.MockTransport`):
  - NDJSON со `thinking` → `content` → `done`: последовательность событий и цифры статистики;
  - `tokens_per_second` считается; при `eval_count=0` → 0;
  - vision: `images` из сообщения попадают в тело запроса;
  - `list_models` парсит `/api/tags`; `health` → True/False на 200/ошибке;
  - сетевой сбой → `OllamaUnavailable`.
- `test_chat_service.py` (`FakeLLMClient`, временный store):
  - первый ход создаёт состояние с системным промптом;
  - второй ход несёт предыдущую историю;
  - `trim` соблюдает лимиты сообщений/символов и сохраняет system;
  - `reset` очищает историю, не трогая system/модель;
  - фото → в истории плейсхолдер `[фото]`;
  - `set_model` валидирует по `list_models`;
  - `stats` содержит модель и tok/s.
- `test_formatter.py`:
  - эскейп `<`,`>`,`&`; `` `code` `` и ``` ```block``` ```; `**bold**`;
  - `split_message` ≤ 4096 и покрывает весь текст без потерь;
  - `footer` с и без статистики.
- `test_streamer.py` (фейковый приёмник фиксирует вызовы):
  - троттлинг: частые `push` не правят слишком часто;
  - идентичный текст не вызывает `edit`;
  - `finish` делает финальный flush и футер;
  - длинный ответ → несколько сообщений.
- `test_vision.py`:
  - `PhotoInput` → base64 (валидное декодирование);
  - дефолтный промпт при пустой подписи.

Запуск: `& ".venv\Scripts\python.exe" -m pytest -q`.

## Демонстрация (видео)

1. `ollama list` / `ollama ps` — модель на месте, работает локально.
2. Запустить бота: лог «Bot started · model=gemma4:12b · Ollama OK».
3. Telegram: `/start` → баннер «локальная модель».
4. Простой вопрос → статус «💭 думает…» → ответ стримится → футер `локально · ⚡ tok/s`.
5. Средний и сложный вопрос → объяснение и код.
6. Отправить **фото** → модель описывает (vision).
7. `/stats` → токены/сек, время (доказательство скорости локально).
8. `/reset` → история очищена. `/model` → смена модели.
9. **Доказательство локальности**: остановить Ollama → отправить сообщение → «⚠️ локальная
   модель не отвечает» → запустить Ollama обратно → снова работает.
10. Стоп записи.

## Критерии готовности

- [ ] `day27/backend/` реализован по структуре выше.
- [ ] Бот отвечает в личке, стрим ответа виден, футер «локальная модель».
- [ ] Память диалога сохраняется на диск и переживает перезапуск.
- [ ] Команды `/start /help /new /model /stats /think /id` работают.
- [ ] Vision: отправленное фото описывается моделью.
- [ ] Работает без облачных LLM (только Ollama на localhost).
- [ ] `pytest -q` зелёный (офлайн, fake LLM + MockTransport), ≥15 тестов.
- [ ] `README.md`, `LESSON.md`, `lesson.html`, `video-script.html`.
- [ ] Строка про День 27 в корневом `README.md`.
- [ ] Коммит и push в `origin/main`.

## Риски и заметки

- **Скорость локальной модели**: `gemma4:12b` на CPU может «думать» заметно; стриминг и
  статус «💭 думает…» скрывают задержку. `num_ctx=8192` вместо дефолтных 262144 экономит
  RAM/VRAM.
- **Thinking-модель**: `content` может стартовать не сразу (сначала идёт `thinking`). Поэтому
  важен статус «думает…»; размышления показываются только при `/think on`.
- **HTML в Telegram**: MarkdownV2 капризен; используем HTML-режим со строгим экранированием и
  фолбэком на плейн-текст.
- **Реальный токен**: для тестов логики не нужен, для демо и автопроверки — нужен в `.env`
  (в git не попадает). Без токена старт падает с понятной ошибкой.
- **Кириллица в CLI**: через `$env:PYTHONIOENCODING="utf-8"`.
- **Токен и приватность**: бот обращается и к Telegram, и к локальной Ollama; наружу уходит
  только трафик Telegram (сама модель — локально, без облачных LLM).
