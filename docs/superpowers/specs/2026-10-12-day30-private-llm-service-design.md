# День 30 — Приватный LLM-сервис на домашнем сервере (дизайн)

## Задача дня

Развернуть локальную LLM как сервис: с HTTP API и возможностью чата. Проверить доступ к
модели по сети, стабильность при нескольких запросах и базовые ограничения (rate limit /
лимит контекста). Результат — приватный AI-сервис на базе локальной LLM.

## Решения, принятые на брейншторме

- **Площадка** — домашний сервер = этот ПК (Windows). Сервис слушает LAN (`0.0.0.0`),
  Ollama остаётся на `localhost`. Реальный VPS и Docker не используем.
- **Интерфейс** — OpenAI-совместимый API (`/v1/chat/completions` со стримингом) плюс
  собственный веб-чат (статика без сборки) плюс `/health` и `/metrics`.

## Идея и архитектура

У Ollama нет авторизации, rate limit, лимита контекста и очереди. Поэтому перед ним ставим
**FastAPI-шлюз**, который добавляет ровно то, что требует задание, и не открывает Ollama
напрямую в сеть.

```
браузер / curl (LAN) ──HTTP + X-API-Key──► [FastAPI-шлюз :8000]
                                             ├─ авторизация (API-ключ)
                                             ├─ rate limit (token bucket)
                                             ├─ лимит контекста (num_ctx, max_tokens)
                                             ├─ защита конкурентности (семафор + очередь)
                                             ├─ /v1/chat/completions  (OpenAI-совместимо, стриминг)
                                             ├─ /v1/models · /health · /metrics
                                             └─ веб-чат (статика)
                                                    │ httpx
                                                    ▼
                                             [Ollama :11434] → gemma4:12b
```

Шлюз — единственный процесс, смотрящий в LAN. Внутренний Ollama-порт остаётся закрытым.

## API

| Метод и путь | Назначение |
|---|---|
| `POST /v1/chat/completions` | OpenAI-совместимый чат. `stream: true` → SSE (`data: {...}` … `data: [DONE]`). |
| `GET /v1/models` | Список локальных моделей Ollama в формате OpenAI (`object: "list"`). |
| `GET /health` | Статус шлюза и Ollama, активная модель, аптайм, версия. |
| `GET /metrics` | Счётчики запросов / 429 / 503, латентности p50/p95, глубина очереди. |
| `GET /` | Веб-чат (статический `frontend/`). |

Ошибки — в формате OpenAI: `{"error": {"message": str, "type": str, "code": str}}`.

## Безопасность и лимиты

- **Авторизация.** Ключи из `.env` (`API_KEYS`, через запятую). Принимаем `X-API-Key` или
  `Authorization: Bearer <key>`. Нет ключа / неверный → `401`. `/health` доступен без ключа
  (нужен для проверки доступности), `/metrics` — только с ключом.
- **Rate limit.** Token bucket на идентичность (ключ, иначе IP): дефолт `30 req/min`,
  burst `10`. Превышение → `429` + `Retry-After`.
- **Лимит контекста.** `NUM_CTX` (8192 по умолчанию), `MAX_TOKENS` дефолт `512`, жёсткий
  потолок `2048`. Оценка токенов промпта эвристикой; если `prompt_tokens + max_tokens >
  NUM_CTX` → `400` с пояснением и подсказкой уменьшить историю/`max_tokens`.
- **Конкурентность.** `MAX_CONCURRENCY` (дефолт `1` — Ollama сериализует) + ограниченная
  очередь `MAX_QUEUE` (дефолт `8`). Переполнение очереди → `503` + `Retry-After`.

## Код (структура `day30/`)

Clean architecture, как в днях 26–29:

```
day30/
  backend/
    app/
      config.py                     # pydantic-settings
      domain/models.py              # ChatMessage, ChatCompletionRequest/Response, Usage
      ports/llm.py                  # LlmGateway (chat, chat_stream, list_models, health)
      application/chat_service.py   # validate → budget → gateway
      application/context.py        # оценка токенов + проверка бюджета
      application/rate_limit.py     # token bucket
      application/concurrency.py    # семафор + ограниченная очередь
      infrastructure/ollama_client.py
      infrastructure/metrics.py     # счётчики + гистограмма латентности
      presentation/app.py           # фабрика FastAPI: middleware, DI, статика
      presentation/routes_chat.py   # /v1/chat/completions, /v1/models
      presentation/routes_admin.py  # /health, /metrics
      presentation/auth.py          # зависимость авторизации
      presentation/errors.py        # OpenAI-формат ошибок
      main.py                       # uvicorn (host из настроек)
    frontend/{index.html,app.js,styles.css}
    scripts/{run_service.ps1,lan_ip.ps1,open_firewall.ps1,stability_test.py,smoke.ps1}
    tests/                          # pytest на httpx ASGITransport
    requirements.txt
    .env.example
  README.md
  LESSON.md
  lesson.html
  video-script.html
```

### Границы юнитов

- `context.py` — чистая функция `estimate_tokens(text)` и `check_budget(messages, max_tokens,
  num_ctx)`; тестируется без сети.
- `rate_limit.py` — `TokenBucket.allow(now) -> (bool, retry_after)`; тестируется с
  инъекцией времени.
- `concurrency.py` — `Guard` со счётчиком + лимитом очереди; `try_acquire()/release()`.
- `ollama_client.py` — httpx к `/api/chat`, `/api/tags`, `/api/ps`; маппинг стрима в
  OpenAI-чанки. Скрыт за портом `LlmGateway`, чтобы тесты подставляли фейк.
- `metrics.py` — счётчики и перцентили из списка латентностей (без внешних зависимостей).
- `presentation/*` — HTTP-обвязка; вся логика в application.

## Проверки, которые показываем

1. **Доступ по сети.** Сервис на `0.0.0.0:8000`; скрипт печатает LAN-IP и делает запрос на
   `http://<LAN-IP>:8000/health` — тем самым идёт через сетевой стек, а не loopback.
   В README — правило firewall (`New-NetFirewallRule`) и вход с телефона по Wi-Fi.
2. **Стабильность.** `scripts/stability_test.py` шлёт 24 параллельных запроса и сообщает
   долю успешных/429/503, p50/p95 латентности и что сервис не упал.
3. **Лимиты.** Онлайн-демо `429` (rate limit) и `400` (контекст), плюс `/metrics`.

## Тесты

Офлайн pytest на `httpx.ASGITransport` с фейковым `LlmGateway`: авторизация (нет/неверный/
верный ключ), rate limit (429 + `Retry-After`), лимит контекста (400), очередь (503),
стриминг SSE, схема OpenAI-ответа и ошибок, `/health`, `/metrics`, `estimate_tokens`.

## Артефакты

`README.md` (запуск, команды, реальные цифры), `LESSON.md`, `lesson.html`,
`video-script.html`, строка в корневом `README.md`.

## Вне рамок (YAGNI)

TLS/HTTPS (в README опишем вариант с Caddy, но ставить не будем), роли и мультипользователи,
персистентный rate-limit (хватит памяти), Docker, реальный VPS, управление моделями, RAG.
