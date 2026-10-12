# День 27 — Telegram-бот на локальной LLM

Telegram-бот, который отвечает через **локальную** модель (`gemma4:12b` в Ollama) — без облачных
LLM. Работает прямо с домашнего компьютера: Telegram → бот (long polling) → Ollama на
`localhost:11434`.

- **текст** → ответ **стримится** в сообщение (видно, как модель печатает);
- **память диалога** на каждый чат, переживает перезапуск;
- **фото** → модель описывает изображение (vision);
- **команды** `/start /help /new /reset /model /stats /think /id`;
- у каждого ответа футер `🤖 gemma4:12b · локально · ⚡ N tok/s` — видно, что модель локальная.

Стек: aiogram 3 (async) + httpx (`/api/chat` стримом) + pydantic-settings. Архитектура —
clean architecture как в других днях: ядро не знает ни про Telegram, ни про HTTP.

## Команды бота

| Команда | Что делает |
|---|---|
| `/start` | приветствие + «я локальная модель», список команд |
| `/help` | справка |
| `/new` (`/reset`) | очистить историю диалога |
| `/model` | показать текущую и доступные модели |
| `/model <имя>` | сменить модель (проверяется по `/api/tags`) |
| `/stats` | модель, скорость последнего ответа (tok/s), размер истории |
| `/think on\|off` | показывать «размышления» модели отдельным сообщением |
| `/id` | id чата |
| *(текст)* | обычный вопрос → ответ со стримингом |
| *(фото)* | описание изображения (подпись к фото — как промпт) |

## Запуск

Нужны: Python 3.11+, запущенная Ollama с моделью `gemma4:12b` (см. День 26) и токен бота от
[@BotFather](https://t.me/BotFather).

```powershell
cd day27/backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env        # вставить TELEGRAM_BOT_TOKEN
.\run_bot.ps1                    # UTF-8 консоль + запуск (или: .venv\Scripts\python.exe -m app.main)
```

> Если `pip` падает с `SSL: CERTIFICATE_VERIFY_FAILED` (корпоративный прокси), добавь
> `--trusted-host pypi.org --trusted-host files.pythonhosted.org`.

В логе увидишь:

```
Ollama: OK (http://localhost:11434)
Модели: gemma4:12b
Модель: gemma4:12b
Bot started. Polling…
```

Открой своего бота в Telegram и напиши `/start`.

## Как это работает

```
Telegram  ⇄  aiogram (presentation)  ⇄  ChatService (application)  ⇄  LLMClient (port)  ⇄  OllamaClient
                        │                        │
                 TelegramStreamer          JsonChatStore
                 (правки/сплит)            (история диалога)
```

- **presentation** — aiogram: команды, текст, фото; правки сообщения для стриминга.
- **application** — сборка запроса (system + история + ход), статистика, обрезка контекста,
  формат ответа; **не знает** про aiogram и httpx.
- **infrastructure** — `OllamaClient` (стрим NDJSON, vision, `/api/tags`) и `JsonChatStore`.
- **ports** — интерфейс `LLMClient`, от которого зависит ядро (поэтому тесты идут без сети).

Стриминг: `ChatService` отдаёт события `content` из Ollama, а `TelegramMessageStreamer`
троттлит `edit_message_text` (раз в ~1.2 с) — ответ «печатается» в чате. Длинные ответы
разбиваются по 4096 символов.

## Почему это локально

Бот обращается к Ollama на `localhost:11434` и **не использует облачные LLM** (нет OpenAI/DeepSeek
и т.п.). Наружу уходит только трафик Telegram. Это видно по:
- футеру каждого ответа — `локально · ⚡ tok/s`;
- `/stats` — скорость генерации с твоей машины;
- если остановить Ollama — бот отвечает «локальная модель не отвечает».

## Тесты

```powershell
cd day27/backend
.venv\Scripts\python.exe -m pytest -q
```

45 офлайн-тестов: клиент Ollama (`httpx.MockTransport`), форматтер, хранилище, сервис диалога
(`FakeLLMClient`), стример, vision, конфиг. Сеть и Telegram не нужны.

## Структура

```
day27/
  README.md  LESSON.md  lesson.html  video-script.html
  backend/
    app/
      main.py                 # точка входа: config → bot → dispatcher → polling
      config.py               # pydantic-settings (.env)
      domain/models.py        # Role, ChatMessage, GenerationStats, ChatState
      ports/llm.py            # LLMClient (Protocol) + события стрима
      infrastructure/
        ollama_client.py      # httpx async: /api/chat (NDJSON), /api/tags, vision
        chat_store.py         # JSON-история в data/chats/<id>.json
      application/
        chat_service.py       # история, запрос, статистика, обрезка
        formatter.py          # markdown→Telegram HTML, split 4096, футер
        vision.py             # base64 фото, дефолтный промпт
      presentation/
        handlers.py           # aiogram: команды, текст, фото
        streamer.py           # троттлинг edit_text, overflow
        middlewares.py        # обработка ошибок
        messages.py           # тексты
    tests/                    # 45 офлайн-тестов
```
