# День 25 — Мини-чат с RAG и памятью задачи (production-like)

## Цель

Построить многопользовательский мини-чат (FastAPI + React), который:

- хранит историю диалога на диске;
- на каждый вопрос ищет контекст через RAG;
- отвечает с учётом найденной информации и **всегда** выводит источники;
- держит «память задачи» (task state) и не теряет цель в длинном диалоге.

Проверка: 2 сценария по 10–15 сообщений; ассистент не теряет цель и каждый ответ
содержит источники.

## Контекст и переиспользование

День 25 — надстройка над Днём 24. Переиспользуем без изменений:

- `RAGAgent` (режимы `rag`/`rag_guard`, цитаты, «не знаю»);
- `JsonRetriever` + индекс Дня 21 (`day21/index/structure.json`);
- `HeuristicReranker`, `LLMRewriter`, `DeepSeekGateway`, `FakeLLM`;
- `extract_citations` (LCS-цитаты, `min_quote_len`).

Новое — сессионный слой: хранение диалога, память задачи, её LLM-апдейт, раннер сценариев.

## Архитектура

```
day25/
  backend/
    app/
      domain/models.py          # Session, Message, TaskMemory, ChatAnswer
      application/
        chat_service.py         # ход диалога: retrieve → answer → update memory
        memory.py               # извлечение/merge TaskMemory из ответа LLM
        scenario_runner.py      # проигрывание сценариев + проверка
      infrastructure/
        session_store.py        # JSON-хранилище сессий на диске
        ... (копии из day24: retrieval, reranker, rewriter, gateways, embeddings)
      presentation/             # routes, schemas, dependencies
      data/
        sessions/               # сюда пишутся сессии
        scenarios/*.json        # 2 сценария
    tests/
  frontend/                     # React/Vite
  README.md  LESSON.md  lesson.html  video-script.html
```

## Модели данных

```python
TaskMemory = {
  "goal": str,            # цель диалога
  "clarifications": [str],# что пользователь уже уточнил
  "constraints": [str],   # зафиксированные ограничения
  "terms": [str],         # зафиксированные термины/решения
}

Message = { role, text, sources: [SourceRef], citations: [Citation], at }

Session = { id, created_at, memory: TaskMemory, messages: [Message] }

SourceRef = { source, section, chunk_id, score }
```

## Цикл одного хода

```
POST /api/sessions/{id}/messages { text }
1. resolve  = текст + последние сообщения истории + память (для ко-референции)
2. rewrite  = LLM → англ. запрос (режим rag_guard из Дня 24)
3. search + rerank + filter (k_pre=30 → k_post=8)
4. prompt   = system + ПАМЯТЬ(блок JSON) + ИСТОРИЯ(вся) + КОНТЕКСТ(RAG) + вопрос
5. answer   = LLM с маркерами [n] → extract_citations → источники
6. memory   = LLM: вернуть обновлённый TaskMemory (merge, не перезапись)
7. save     = сессия пишется в data/sessions/{id}.json
```

Три LLM-вызова на ход: `rewrite`, `answer`, `memory-update`. `memory-update` получает
текущую память + новый вопрос/ответ и возвращает JSON `{goal, clarifications,
constraints, terms}`. Пустые списки сохраняются, отсутствующие ключи — нет (не теряем
существующие).

Память подаётся в промпт как JSON-блок; история — целиком (сценарии ≤15 сообщений).

## API

| Метод | Путь | Описание |
|---|---|---|
| POST | `/api/sessions` | `{goal}` → новая сессия с начальной памятью `{goal, [], [], []}` |
| POST | `/api/sessions/{id}/messages` | `{text}` → ответ, источники, цитаты, обновлённая память |
| GET | `/api/sessions/{id}` | полная сессия |
| GET | `/api/sessions` | список сессий (id, created_at, goal, n_messages) |
| POST | `/api/scenarios/run` | прогнать сценарии, вернуть отчёт (использует тот же ChatService) |

## Frontend (React/Vite)

- Список сессий + «Новая сессия» (ввод цели).
- Чат: история, у каждого ответа ассистента — источники и цитаты.
- Панель «Память задачи»: цель, уточнения, ограничения, термины; обновляется после хода.

## Проверка (2 сценария)

Сценарии в `data/scenarios/*.json` — массивы `{role:"user", text}`. Раннер проигрывает их
через `ChatService` и собирает отчёт. Обязательные проверки:

1. **Источники всегда есть**: каждый ответ ассистента имеет ≥1 источник.
2. **Цель не потеряна**: `memory.goal` в конце сценария непустой и совпадает по смыслу с
   начальной целью (совпадение по ключевым словам/подстроке).
3. **Память накапливается**: `constraints`/`clarifications` не пусты к концу сценария.

Сценарий 1 «Настройка KMP-проекта под Android и iOS» (≈12 сообщений):
цель — минимальный рабочий KMP-проект; пользователь уточняет таргеты, expect/actual,
подключение библиотек, фиксирует ограничение «только Kotlin 2.0», в конце просит итог.

Сценарий 2 «Сетевой слой на Ktor + корутины» (≈12 сообщений):
цель — единый сетевой код в commonMain; уточняются зависимости Ktor, Dispatchers,
HttpClient, сериализация, фиксируется «минимальная iOS 15», в конце просит итог.

## Тесты (офлайн, pytest)

- `test_memory.py` — извлечение/merge TaskMemory из JSON-ответа, сохранение существующих полей.
- `test_chat_service.py` — ход диалога на `FakeLLM` + фикстурный индекс: возвращает
  ответ, источники, обновлённую память.
- `test_session_store.py` — create/get/list, персист на диск.
- `test_scenario_runner.py` — оба сценария на FakeLLM дают отчёт с `passed=True`.

## Ограничения и YAGNI

- Окно истории не вводим (вся история).
- Нет авторизации/юзеров — сессии адресуются по id.
- Нет стриминга токенов.
- `memory-update` — один вызов LLM, без ретраев.
