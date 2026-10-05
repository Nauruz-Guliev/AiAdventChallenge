# День 23 — Реранкинг и фильтрация (урок)

## Идея

RAG из Дня 22 ищет top-k по векторному сходству и сразу кладёт результат в контекст.
Проблема: векторный поиск не гарантирует, что в топе окажутся действительно релевантные
чанки, и не умеет уточнять запрос. День 23 добавляет **два этапа**:

1. **query rewrite** — до поиска переформулируем вопрос в англоязычный поисковый запрос;
2. **фильтр + heuristic-реранкинг** — после поиска отсекаем нерелевантное по порогу и
   пересортировываем оставшееся.

```
вопрос → [rewrite → запрос] → поиск top-K_pre → фильтр → реранк → top-K_post → LLM
```

## Компоненты (backend)

- `app/application/agent.py` — `RAGAgent.answer(question, mode)` с 5 режимами:
  `no_rag`, `rag`, `rag_filter`, `rag_rewrite`, `rag_full`.
- `app/application/query_rewriter.py` — `QueryRewriter.rewrite()`: LLM переводит вопрос
  в короткий англ. запрос; при пустом ответе — fallback на исходный вопрос.
- `app/infrastructure/heuristic_reranker.py` — `HeuristicReranker` + `filter_by_threshold`.
- `app/application/evaluator.py` — прогон 10 вопросов по всем режимам, LLM-судья (0…1),
  покрытие источников, сводка по режимам.
- `app/infrastructure/retrieval.py` — `JsonRetriever` (индекс Дня 21, cosine через numpy).
- `app/presentation/` — FastAPI: `/api/answer` (все режимы), `/api/questions`, `/api/eval`.

## Фильтр и реранкинг

- **K_pre** (до фильтра) = 30, **K_post** (после) = 8.
- **Порог** `min_sim` (cosine) — хиты ниже отбрасываются.
- **Heuristic-скор** каждого выжившего хита:

```
sim  = векторный cosine
lex  = доля терминов запроса, найденных в тексте чанка
head = 1, если термин запроса есть в title/section, иначе 0

final = 0.6·sim + 0.3·lex + 0.1·head
```

- **Fallback**: если фильтр отбросил всё — берём исходные top-K_post.

Почему `lex` имеет смысл: доки на английском, поэтому лексическое пересечение считаем
по **переписанному** англоязычному запросу; идентификаторы KMP (expect/actual, commonMain,
Ktor, Compose, Maven, CocoaPods) языково нейтральны.

## Пять режимов

| Режим | Rewrite | Фильтр+реранк |
|---|---|---|
| `no_rag` | — | — |
| `rag` | — | — |
| `rag_filter` | — | да |
| `rag_rewrite` | да | — |
| `rag_full` | да | да |

## Оценка и сравнение

1. По каждому вопросу — ответ во всех 5 режимах.
2. **LLM-судья** ставит 0…1 каждому ответу против ожидания.
3. **Покрытие источников** — попали ли ожидаемые файлы в top-K_post (для RAG-режимов).

Сводка по каждому режиму: `avg_score` и `source_coverage_rate`.

## Как воспроизвести

```powershell
cd day23/backend
python -m venv .venv
& .venv/Scripts/python.exe -m pip install -r requirements.txt
copy .env.example .env    # впиши DEEPSEEK_API_KEY

# индекс нужен из Дня 21 (../../day21/index/structure.json)
cd ../day21
& .venv/Scripts/python.exe pipeline.py --strategy both --embedder sentence

cd ../day23/backend
& .venv/Scripts/python.exe -m uvicorn app.main:app --port 8000
```

В другом окне:

```powershell
cd day23/frontend
npm install
npm run dev
```

## Результаты (реальный прогон)

| Режим | Средний балл | Покрытие источников |
|---|---|---|
| без RAG | 0.98 | — |
| RAG (baseline) | 0.83 | 0.80 |
| RAG + фильтр/реранк | 0.81 | 0.90 |
| RAG + rewrite | 0.75 | 0.80 |
| RAG + rewrite + фильтр | 0.81 | 0.90 |

**Разбор.** Фильтр + реранкинг поднимают **покрытие источников** с 0.80 до 0.90 — поиск
находит нужные документы точнее. Средний балл почти не меняется (0.83 → 0.81): модель и так
отвечает хорошо, а судья оценивает ответ, а не сам факт ссылок. Rewrite в одиночку чуть
проседает по баллу, но поднимает профильный документ в топ. Вывод: второй этап улучшает
**precision поиска и надёжность ссылок**, а не сырой балл. Порог и веса (`MIN_SIM`,
`W_SIM/W_LEX/W_HEAD`) настраиваются в `.env`.

## Тесты

```powershell
cd day23/backend
& .venv/Scripts/python.exe -m pytest -q
```

## Что дальше

- cross-encoder ре-ранкинг (отдельная модель вместо heuristic);
- гибридный поиск (BM25 + вектор);
- соседние чанки в контекст (расширение окна вокруг найденного).
