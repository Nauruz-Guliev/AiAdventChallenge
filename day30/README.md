# День 30 — Приватный LLM-сервис на домашнем сервере

Разворачиваем локальную модель (`gemma4:12b` через Ollama) как **сетевой сервис**: HTTP API с
чат-эндпоинтом, авторизацией, rate limit, лимитом контекста и очередью — плюс веб-страница чата.
Проверяем доступ по сети, стабильность под нагрузкой и базовые ограничения.

Стек: FastAPI + uvicorn + httpx + pydantic v2 (backend), статический чат без сборки (frontend),
Ollama как рантайм модели. Архитектура — clean architecture, как в остальных днях.

## Идея

Сам по себе Ollama отдаёт модель по HTTP, но у него **нет** авторизации, ограничений частоты,
лимита контекста и очереди. Поэтому наружу выставлен не Ollama, а **FastAPI-шлюз**, который
добавляет ровно эти вещи. Ollama остаётся на `localhost` и в сеть не смотрит.

```
браузер / curl (в LAN) ──HTTP + X-API-Key──► [FastAPI-шлюз :8000]
                                              ├─ авторизация по API-ключу
                                              ├─ rate limit (token bucket)
                                              ├─ лимит контекста (num_ctx, max_tokens)
                                              ├─ защита конкурентности (семафор + очередь)
                                              ├─ /v1/chat/completions (OpenAI-совместимо + SSE)
                                              ├─ /v1/models · /health · /metrics
                                              └─ веб-чат (статика)
                                                     │ httpx
                                                     ▼
                                              [Ollama :11434] → gemma4:12b
```

## API

| Метод и путь | Что делает |
|---|---|
| `POST /v1/chat/completions` | OpenAI-совместимый чат. `stream: true` → SSE (`data: {...}` … `data: [DONE]`). |
| `GET /v1/models` | Список локальных моделей в формате OpenAI. |
| `GET /health` | Статус шлюза и Ollama, активная модель, аптайм (без ключа). |
| `GET /metrics` | Счётчики запросов/429/503, p50/p95 латентности, глубина очереди. |
| `GET /` | Веб-чат. |

Ошибки — в формате OpenAI: `{"error": {"message", "type", "code"}}`.

## Ограничения (базовые)

| Ограничение | Значение по умолчанию | Поведение при превышении |
|---|---|---|
| Авторизация | `API_KEYS` из окружения | `401 invalid_api_key` |
| Rate limit | 30 req/min, burst 10 (token bucket на ключ/IP) | `429` + `Retry-After` |
| Контекст | `NUM_CTX=8192`, `MAX_TOKENS` 512 (потолок 2048) | `400 context_length_exceeded` |
| Конкурентность | `MAX_CONCURRENCY=1`, очередь `MAX_QUEUE=8` | `503` + `Retry-After` |

Ключ принимается как `X-API-Key`, так и `Authorization: Bearer …`. Лимит считается на ключ
(если ключей нет — на IP). `MAX_CONCURRENCY=1`, потому что Ollama сериализует генерацию.

## Структура

```
day30/
  backend/
    app/
      config.py                     # настройки (pydantic-settings)
      domain/models.py              # ChatMessage, Completion, Usage, ошибки сервиса
      ports/llm.py                  # протокол LlmGateway
      application/
        context.py                  # оценка токенов и бюджет контекста
        rate_limit.py               # token bucket
        concurrency.py              # семафор + ограниченная очередь
        chat_service.py             # валидация → бюджет → шлюз
      infrastructure/
        ollama_client.py            # httpx к /api/chat, /api/tags, /api/ps
        metrics.py                  # счётчики и перцентили
      presentation/
        app.py                      # фабрика FastAPI, middleware, статика
        routes_chat.py              # /v1/chat/completions, /v1/models
        routes_admin.py             # /health, /metrics
        auth.py, errors.py, schemas.py
      main.py                       # uvicorn (host из настроек)
    frontend/                       # index.html + app.js + styles.css (без сборки)
    scripts/                        # run_service, lan_ip, open_firewall, smoke, stability_test
    tests/                          # 57 офлайн-тестов
    requirements.txt
  README.md · LESSON.md · lesson.html · video-script.html
```

## Демо одной командой

```powershell
cd day30
.\demo.ps1
```

Скрипт проверит Ollama, поднимет шлюз и **сам откроет чат в браузере с уже введённым ключом**
(`demo-key`) — настраивать ничего не нужно. Плюс напечатает ссылку для телефона в той же Wi-Fi.
Остановить: `.\stop_demo.ps1` или закрыть минимизированное окно Python.

## Запуск

Требуется Ollama с моделью:

```powershell
ollama list                 # должна быть gemma4:12b
ollama pull gemma4:12b      # если нет
```

Затем:

```powershell
cd day30/backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.\scripts\run_service.ps1                            # поднимет http://0.0.0.0:8000
```

Ключ доступа задаётся переменной окружения `API_KEYS` (через запятую для нескольких):

```powershell
$env:API_KEYS = "my-secret-key"; .\scripts\run_service.ps1
```

> Без `API_KEYS` сервис работает анонимно и печатает предупреждение — только для локальной отладки.

> `pip` при корпоративном SSL: добавь `--trusted-host pypi.org --trusted-host files.pythonhosted.org`.

### Доступ по сети (LAN)

```powershell
.\scripts\lan_ip.ps1        # покажет IP этой машины, напр. <INTERNAL_IP>
.\scripts\open_firewall.ps1 # откроет порт 8000 в брандмауэре (нужны права админа)
```

С другого устройства в той же Wi-Fi-сети: `http://<IP>:8000/` — откроется чат. Ключ вводится в
поле слева и хранится в браузере (`localStorage`). Ollama при этом в сеть не выставлен — только шлюз.

### Проверка API из консоли

```powershell
.\scripts\smoke.ps1 -Key my-secret-key                     # health + один чат-запрос
.venv\Scripts\python.exe scripts\stability_test.py --requests 24 --workers 12
```

## Результаты реальной проверки

Машина: домашний сервер (Windows), модель `gemma4:12b` (Q4_K_M, ~8 ГБ), `localhost:11434`.

**Доступ по сети.** `GET http://<INTERNAL_IP>:8000/health` вернул
`{"status":"ok","ollama":true,...}` — запрос прошёл через сетевой интерфейс (не loopback).
Без ключа `/v1/models` → `401`, с ключом → список моделей.

**Стабильность.** `stability_test.py --requests 24 --workers 12` (24 одновременных запроса):

| Метрика | Значение |
|---|---|
| `200 OK` | 11 (46%) |
| `429 Too Many Requests` (rate limit) | 12 (50%) |
| `503 Service Unavailable` (очередь переполнена) | 1 (4%) |
| Латентность p50 | 3167 мс |
| Латентность p95 | 4534 мс |
| Сервис после нагрузки | `status: ok`, очередь пуста (`active_requests: 0`) |

Дальнейшие запросы шли нормально: `expected` (после окна rate limit). Ни одного падения, ни
`0`/таймаута — при 24 параллельных запросах шлюз **деградирует управляемо** (429/503), а не падает.

**Метрики** после нагрузки: `requests_total 17 · success_total 15 · rate_limited_total 12 ·
overloaded_total 1 · latency_ms_p50 686 · latency_ms_p95 1378`.

**Лимиты вживую.**
- Rate limit: 40 быстрых запросов → часть получает `429` с `Retry-After`.
- Контекст: сообщение на 40 000 символов → `400`
  (`~10004 токенов + max_tokens 512 превышает num_ctx 8192`).

## Тесты

```powershell
cd day30/backend
.venv\Scripts\python.exe -m pytest -q       # 57 passed
```

Офлайн-тесты (сеть и модель не нужны, Ollama подменяется фейковым шлюзом): бюджет контекста,
token bucket, очередь/перегрузка, метрики, клиент Ollama (httpx MockTransport), схема
OpenAI-ответов и ошибок, авторизация, эндпоинты (`/health`, `/v1/models`, чат, `429`, `503`,
`400`), SSE-стриминг, раздача статики.

## Вне рамок

TLS/HTTPS (проще всего поставить перед шлюзом Caddy — см. `LESSON.md`), роли и
мультипользователи, персистентный rate limit (хватает памяти), Docker, управление моделями, RAG.
