# День 25 — Мини-чат с RAG и памятью задачи

Мини-чат (FastAPI + React), который ведёт многоходовой диалог поверх RAG:

- хранит **историю диалога** на диске (JSON);
- на каждый вопрос ищет контекст через RAG;
- отвечает с учётом найденной информации и **всегда** выводит источники и цитаты;
- держит **«память задачи»** (task state): цель, уточнения, ограничения, термины —
  обновляется LLM каждый ход и не теряется в длинном диалоге.

Проверка — 2 сценария по 11 сообщений: ассистент не теряет цель и продолжает давать
ответы с источниками.

Стек: FastAPI (backend) + React/Vite (frontend), LLM — DeepSeek API. Индекс и RAG-пайплайн
переиспользованы из Дней 21–24.

## Как это работает

```
вопрос → [rewrite с целью] → поиск → реранк → фильтр
       → промпт = системный + ПАМЯТЬ(JSON) + ИСТОРИЯ(вся) + КОНТЕКСТ(RAG) + вопрос
       → LLM-ответ с маркерами [n] → цитаты (LCS с чанком)
       → LLM-апдейт памяти (merge, не перезапись)
       → сессия сохраняется на диск
```

Три LLM-вызова на ход: `rewrite`, `answer`, `memory-update`.

### Память задачи (task state)

```json
{
  "goal": "Настроить минимальный рабочий KMP-проект для Android и iOS",
  "clarifications": ["нужны таргеты Android и iOS", "..."],
  "constraints": ["только Kotlin 2.0"],
  "terms": ["expect/actual", "commonMain"]
}
```

- `goal` — цель диалога; задаётся при создании сессии и **не теряется** (если апдейт
  вернул пустую цель — сохраняется старая).
- `clarifications` / `constraints` / `terms` — накапливаются (union без дублей).

## API

| Метод | Путь | Что делает |
|---|---|---|
| POST | `/api/sessions` | `{goal}` → новая сессия |
| POST | `/api/sessions/{id}/messages` | `{text}` → ответ + источники + цитаты + обновлённая память |
| GET | `/api/sessions/{id}` | полная сессия (история + память) |
| GET | `/api/sessions` | список сессий |
| POST | `/api/scenarios/run` | прогнать 2 сценария, вернуть отчёт |

## Структура

```
day25/
  backend/
    app/
      domain/models.py            # Hit, Citation, Message, TaskMemory, Session, ChatTurn
      application/
        chat_service.py           # ход диалога: retrieve → answer → citations → memory
        memory.py                 # MEMORY_SYSTEM, parse/merge TaskMemory
        scenario_runner.py        # проигрывание сценариев + проверки
        citation.py, query_rewriter.py   # переиспользованы из Дня 24
      infrastructure/
        session_store.py          # JSON-хранилище сессий (data/sessions)
        retrieval.py, heuristic_reranker.py, embeddings.py, deepseek_gateway.py, fake_llm.py
        settings.py
      ports/                      # llm_gateway, retriever, reranker, rewriter
      presentation/               # routes, schemas, dependencies
      data/scenarios/             # scenario_android_ios.json, scenario_ktor.json
    tests/
  frontend/                       # React: чат + панель памяти + сценарии
  README.md  LESSON.md  lesson.html  video-script.html
```

## Установка и запуск

Команды — в PowerShell, backend и frontend в двух окнах.

### 1. Backend

```powershell
cd day25/backend
python -m venv .venv
& .venv/Scripts/python.exe -m pip install -r requirements.txt

copy .env.example .env
# открой .env и впиши DEEPSEEK_API_KEY

& .venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Нужен индекс Дня 21 (`../../day21/index/structure.json`). Если его нет — собери в `day21`.

### 2. Frontend

```powershell
cd day25/frontend
npm install
npm run dev      # http://localhost:5173
```

### Офлайн-режим (без ключа)

В `.env` поставь `LLM_PROVIDER=fake` — ответы и апдейты памяти даёт детерминированная заглушка.

## Настройки (.env)

| Переменная | По умолчанию | Что делает |
|---|---|---|
| `NO_ANSWER_MIN_SCORE` | 0.60 | порог релевантности для «не знаю» |
| `MIN_QUOTE_LEN` | 24 | мин. длина дословной цитаты |
| `K_PRE` / `K_POST` | 30 / 8 | top-k до/после фильтра |
| `SESSIONS_DIR` | data/sessions | где лежат сессии |
| `SCENARIOS_DIR` | app/data/scenarios | где лежат сценарии |

## Проверка: 2 сценария × 11 сообщений

Сценарии в `data/scenarios/*.json`, запуск — `POST /api/scenarios/run` (или вкладка
«Сценарии» во фронтенде). Раннер проигрывает каждый сценарий через `ChatService` и
проверяет три условия:

1. **Источники всегда есть** — у каждого ответа ассистента ≥ 1 источника.
2. **Цель не потеряна** — `memory.goal` в конце непустой и пересекается с начальной целью.
3. **Память накопилась** — к концу сценария есть хотя бы одно уточнение/ограничение/термин.

`passed = источники всегда И цель сохранена И память накоплена`.

Сценарий 1 — «Настройка KMP-проекта под Android и iOS»: таргеты, commonMain,
expect/actual, ограничение «Kotlin 2.0», итог.

Сценарий 2 — «Сетевой слой на Ktor + корутины»: зависимости Ktor, HttpClient,
сериализация, ограничение «iOS 15», итог.

## Тесты

```powershell
cd day25/backend
& .venv/Scripts/python.exe -m pytest -q
```

Все тесты офлайн (FakeLLM + фикстурный индекс): память, хранилище сессий, `ChatService`,
сценарии, роуты.
