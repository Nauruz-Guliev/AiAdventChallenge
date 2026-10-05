# День 23 — Реранкинг и фильтрация (дизайн)

## Цель

Улучшить RAG Дня 22, добавив после векторного поиска второй этап —
**фильтр релевантности + heuristic-реранкинг**, а перед поиском — **query rewrite**.
Сравнить качество ответов по режимам: без фильтра/rewrite и с ними.

## Стек и база

Тот же, что и в Дне 22: Python 3.11, FastAPI, pydantic v2, numpy,
sentence-transformers (multilingual MiniLM), DeepSeek API + FakeLLM, React/Vite.
Индекс — готовый из Дня 21 (`day21/index/structure.json`). Папка — новая `day23/`
(копия `day22/` как база, плюс новые модули).

## Пайплайн

```
вопрос
  → [query rewrite (LLM)]  → поисковый запрос (англ. термины KMP)
  → эмбеддинг запроса
  → векторный поиск top-K_pre (K_pre = 30)
  → фильтр по порогу cosine (min_sim, default 0.35)
  → heuristic-реранкинг оставшихся
  → top-K_post (K_post = 8)
  → контекст
  → LLM
  → ответ + источники
```

## Режимы (для сравнения)

| Режим | Rewrite | Фильтр | Рерanking |
|---|---|---|---|
| `no_rag` | — | — | — |
| `rag` | — | — | — |
| `rag_filter` | — | да | да |
| `rag_rewrite` | да | — | — |
| `rag_full` | да | да | да |

- `no_rag` — референс (чистый LLM, без поиска).
- `rag` — baseline Дня 22 (top_k = 8, без фильтра и rewrite) — «качество до».
- `rag_filter` — вклад фильтра+реранкинга без rewrite.
- `rag_rewrite` — вклад только rewrite.
- `rag_full` — итоговый «улучшенный RAG».

## Фильтр релевантности

- `K_pre` — сколько хитов берём из векторного поиска до фильтра (default 30).
- `K_post` — сколько оставляем после фильтра и реранкинга (default 8).
- `min_sim` — порог cosine; хиты со `score < min_sim` отбрасываются.
- **Fallback**: если после фильтра не осталось ни одного хита — берём исходные
  top-K_post (ответ не ломается).

## Heuristic-реранкинг

Скоринг каждого выжившего хита по запросу, который реально использовался для
поиска (переписанному, если rewrite включён, иначе исходному):

- `sim` — векторный cosine, [0, 1];
- `lex` — доля значимых термов запроса, найденных в тексте чанка, [0, 1]
  (значимый терм: буквенно-цифровой токен длиной ≥ 3, lower case);
- `head` — 1.0, если хотя бы один терм запроса есть в `title` или `section`,
  иначе 0.0.

```
final = w_sim * sim + w_lex * lex + w_head * head
w_sim = 0.6, w_lex = 0.3, w_head = 0.1   (настраивается)
```

Хиты сортируются по `final` по убыванию, берётся top-K_post.

Обоснование: доки на английском, вопрос — на русском. Поэтому `lex` считается по
переписанному англоязычному запросу; технические идентификаторы (expect/actual,
commonMain, Ktor, Compose, Maven, CocoaPods, kotlinx.serialization) языково нейтральны.

## Query rewrite

- Отдельный компонент `QueryRewriter` поверх `LLMGateway`.
- System-промпт: «Переформулируй вопрос в короткий англоязычный поисковый запрос
  из ключевых терминов Kotlin Multiplatform. Верни только запрос, без пояснений.»
- Возвращает строку `search_query`; при пустом ответе — fallback на исходный вопрос.
- Через `FakeLLM` — детерминированный результат для тестов.

## Оценка и сравнение

- Метрики на вопрос: оценка LLM-судьи (0…1) и `source_coverage` (все ожидаемые
  источники попали в top-K_post).
- `Evaluator` прогоняет все 5 режимов по 10 контрольным вопросам.
- Сводка по режимам: `questions`, `avg_score`, `source_coverage_rate`.
- Отчёт `data/eval_report.json` (кэш; `?force=1` — пересчёт).

## Структура

```
day23/
  backend/
    app/
      domain/models.py               # mode Literal +5, поля EvalItem под режимы
      ports/retriever.py             # без изменений
      ports/llm_gateway.py
      ports/reranker.py              # НОВЫЙ: Reranker.rerank(query, hits) -> hits
      ports/rewriter.py              # НОВЫЙ: Rewriter.rewrite(question) -> str
      infrastructure/settings.py     # min_sim, k_pre, k_post, веса, rewrite
      infrastructure/retrieval.py
      infrastructure/embeddings.py
      infrastructure/deepseek_gateway.py
      infrastructure/fake_llm.py
      infrastructure/heuristic_reranker.py   # НОВЫЙ
      application/query_rewriter.py  # НОВЫЙ (LLM rewrite)
      application/agent.py           # 5 режимов
      application/evaluator.py       # по всем режимам
      presentation/{schemas,routes,dependencies}.py
      data/eval_questions.json       # те же 10 вопросов
    tests/                           # ~25-30 офлайн-тестов
    requirements.txt
    .env.example
  frontend/                          # React: вкладки «Вопрос» и «Сравнение режимов»
  README.md, LESSON.md, lesson.html, video-script.html
```

## Обработка ошибок

- `IndexNotFound` → 503 (как в Дне 22).
- Пустой вопрос → 422 (валидация pydantic).
- Пустой результат rewrite → fallback на исходный вопрос.
- Пустой результат фильтра → fallback на top-K_post без фильтра.
- Ошибка LLM (judge/answer/rewrite) → существующая обработка `LLMGatewayError`.

## Тесты (офлайн, FakeLLM + фикстурный индекс)

- `heuristic_reranker`: детерминированный скор, сортировка, `head`-бонус.
- фильтр: отсечение по порогу, fallback при пустом результате.
- `query_rewriter`: с FakeLLM и fallback.
- `agent`: ответ по каждому из 5 режимов, источники, число хитов ≤ K_post.
- `evaluator`: сводка по режимам, `source_coverage`.
- `routes`: `/api/answer` (все режимы), `/api/questions`, `/api/eval` + кэш.

## Значения по умолчанию

`min_sim = 0.35`, `k_pre = 30`, `k_post = 8`,
`w_sim = 0.6`, `w_lex = 0.3`, `w_head = 0.1` — настраиваются через `settings`/`.env`.
Порог и веса уточняются по результатам сравнения режимов.

## Вне рамок

- Cross-encoder реранкер (отдельная модель) — сознательно не берём (офлайн, без
  тяжёлых загрузок).
- Гибридный BM25-поиск и изменение размера чанков — вне Дня 23.
