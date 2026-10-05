# День 23 — Реранкинг и фильтрация

Улучшаем RAG из Дня 22 двумя приёмами:

- **фильтр релевантности + heuristic-реранкинг** — после векторного поиска отсекаем
  нерелевантное по cosine-порогу и пересортировываем оставшееся по пересечению терминов;
- **query rewrite** — перед поиском переформулируем вопрос в англоязычный поисковый запрос.

Один вопрос — **пять режимов**, и по 10 контрольным вопросам сравниваем их качество.

Стек: FastAPI (backend) + React/Vite (frontend), LLM — DeepSeek API.

## Как это работает

```
вопрос → [rewrite → запрос] → эмбеддинг → поиск top-K_pre
       → фильтр по порогу → heuristic-реранкинг → top-K_post
       → контекст → LLM → ответ + источники
```

- Индекс готовый из Дня 21: `day21/index/structure.json` (4817 чанков).
- Эмбеддинги — `paraphrase-multilingual-MiniLM-L12-v2`.
- Фильтр: `MIN_SIM` (порог cosine), `K_PRE` (до) = 30, `K_POST` (после) = 8.
- Рерanking: `final = 0.6·sim + 0.3·lex + 0.1·head` (lex — пересечение терминов запроса с текстом, head — бонус за заголовок/секцию).
- Rewrite: тот же DeepSeek переводит вопрос в короткий англ. запрос.

## Пять режимов

| Режим | Rewrite | Фильтр+реранк |
|---|---|---|
| `no_rag` | — | — |
| `rag` | — | — |
| `rag_filter` | — | да |
| `rag_rewrite` | да | — |
| `rag_full` | да | да |

## Структура

```
day23/
  backend/   FastAPI: agent (5 режимов), query_rewriter, heuristic_reranker,
             evaluator (сравнение режимов), DeepSeek gateway (+ FakeLLM)
  frontend/  React: вкладка «Вопрос» (5 панелей) и «Сравнение режимов»
```

## Установка и запуск

Все команды — в PowerShell. Backend и frontend в двух окнах.

### 1. Backend

```powershell
cd day23/backend
python -m venv .venv
& .venv/Scripts/python.exe -m pip install -r requirements.txt

copy .env.example .env
# открой .env и впиши DEEPSEEK_API_KEY

& .venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Нужен индекс Дня 21. Если его нет — собери:

```powershell
cd ../day21
& .venv/Scripts/python.exe pipeline.py --strategy both --embedder sentence
```

### 2. Frontend

```powershell
cd day23/frontend
npm install
npm run dev
```

Открой http://localhost:5173 — вкладка «Вопрос» (пять режимов) и «Сравнение режимов».

### Офлайн-режим (без ключа)

В `.env` поставь `LLM_PROVIDER=fake` — ответы даёт детерминированная заглушка.

## API

| Метод | Путь | Что делает |
|---|---|---|
| POST | `/api/answer` | `{question}` → ответы всех 5 режимов + источники |
| GET | `/api/questions` | список 10 контрольных вопросов |
| POST | `/api/eval` | прогон 10 вопросов по 5 режимам, пишет `data/eval_report.json` (кэш; `?force=1` — пересчёт) |

## Результаты реального прогона

Средние по 10 вопросам (DeepSeek-судья, 0…1):

| Режим | Средний балл | Покрытие источников |
|---|---|---|
| без RAG | **0.98** | — |
| RAG (baseline) | **0.83** | 0.80 |
| RAG + фильтр/реранк | **0.81** | **0.90** |
| RAG + rewrite | **0.75** | 0.80 |
| RAG + rewrite + фильтр | **0.81** | **0.90** |

**Вывод.** Фильтр + heuristic-реранкинг поднимают **покрытие источников** с 0.80
до 0.90 (retrieval находит нужные доки точнее), но средний балл судьи почти не меняется
(0.83 → 0.81) — ответы и так сильны. Rewrite в одиночку чуть проседает по баллу, зато
поднимает профильный документ в топ. Итог: польза второго этапа — **точность поиска и
ссылок на источники**, а не сырой балл ответа. Порог и веса (`MIN_SIM`, `W_SIM/W_LEX/W_HEAD`)
настраиваются в `.env`.

## Тесты

```powershell
cd day23/backend
& .venv/Scripts/python.exe -m pytest -q
```

Все тесты офлайн (FakeLLM + фикстурный индекс).
