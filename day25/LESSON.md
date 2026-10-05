# День 25 — Мини-чат с RAG и памятью задачи (урок)

## Идея

До сих пор RAG отвечал на один вопрос. Но реальный чат — это многоходовый диалог, в котором
нужно помнить, зачем пользователь пришёл, что он уже уточнил и какие ограничения наложил.
День 25 делает мини-чат: история на диске, RAG на каждом вопросе, источники в каждом ответе
и **память задачи** (task state), которая живёт между ходами.

## Что такое «память задачи»

Отдельный структурированный блок, который подаётся в промпт и обновляется LLM каждый ход:

```json
{ "goal": "...", "clarifications": [...], "constraints": [...], "terms": [...] }
```

- `goal` — цель диалога (задаётся при создании сессии, не теряется).
- `clarifications` — что пользователь уже уточнил.
- `constraints` — зафиксированные ограничения.
- `terms` — зафиксированные термины/решения.

## Компоненты (backend)

- `application/memory.py` — `MEMORY_SYSTEM`, `parse_memory`, `merge_memory`
  (merge сохраняет цель, если новая пустая; списки — union без дублей).
- `application/chat_service.py` — `ChatService.answer(session, text)`:
  rewrite → search → rerank → filter → prompt(память+история+контекст+вопрос) →
  answer → citations → memory-update. Плюс порог «не знаю».
- `infrastructure/session_store.py` — JSON-хранилище сессий (`data/sessions/{id}.json`).
- `application/scenario_runner.py` — проигрывание сценариев и проверки.
- `presentation/` — роуты сессий и сценариев.

## Цикл одного хода

```
вопрос → [rewrite с целью] → поиск k_pre → реранк → фильтр k_post
       → промпт = системный + ПАМЯТЬ(JSON) + ИСТОРИЯ + КОНТЕКСТ(RAG) + вопрос
       → LLM-ответ с маркерами [n] → LCS-цитаты
       → LLM-апдейт памяти → merge → save
```

Три LLM-вызова на ход: rewrite, answer, memory-update. История подаётся целиком
(сценарии ≤15 сообщений), память — JSON-блоком.

## Как не потерять цель

1. Цель хранится в `memory.goal`, а не в тексте диалога.
2. `merge_memory` сохраняет старую цель, если LLM вернул пустую.
3. Цель подмешивается в `rewrite` (улучшает поиск) и в системный промпт ответа.

## Проверка: 2 сценария × 11 сообщений

Раннер проигрывает сценарий и проверяет три условия, `passed = все три`:

1. `all_with_sources` — у каждого ответа ассистента есть ≥1 источник.
2. `goal_kept` — итоговая цель непустая и пересекается с начальной.
3. `memory_grown` — память накопила уточнения/ограничения/термины.

## Как воспроизвести

```powershell
cd day25/backend
python -m venv .venv
& .venv/Scripts/python.exe -m pip install -r requirements.txt
copy .env.example .env    # впиши DEEPSEEK_API_KEY

# индекс нужен из Дня 21 (../../day21/index/structure.json)
& .venv/Scripts/python.exe -m uvicorn app.main:app --port 8000
```

Другое окно:

```powershell
cd day25/frontend
npm install
npm run dev
```

Запуск сценариев — вкладка «Сценарии» или `POST /api/scenarios/run`.

## Тесты

```powershell
cd day25/backend
& .venv/Scripts/python.exe -m pytest -q
```

## Что дальше

- скользящее окно истории вместо полной;
- многопользовательская авторизация;
- стриминг токенов ответа.
