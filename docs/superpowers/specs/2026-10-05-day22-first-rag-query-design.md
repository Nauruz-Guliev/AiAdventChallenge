# День 22 — Первый RAG-запрос (дизайн)

## Цель

Реализовать агента с двумя режимами ответа на вопрос по базе документов KMP
(из Дня 21):

- **без RAG** — вопрос напрямую в LLM;
- **с RAG** — вопрос → поиск релевантных чанков → контекст + вопрос → LLM.

Сравнить качество двух режимов на мини-наборе из 10 контрольных вопросов, для
каждого из которых зафиксированы ожидание и ожидаемые источники. Результат —
интерактивное приложение (FastAPI + React) для показа ответов и сравнения.

## Стек и конвенции

- Python + FastAPI + React (Vite) — как дни 6–15.
- LLM — **DeepSeek API** (OpenAI-совместимый клиент), ключ в `backend/.env`
  (`DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL` по умолчанию `deepseek-chat`,
  `DEEPSEEK_BASE_URL` по умолчанию `https://api.deepseek.com`).
- Детерминированная **FakeLLM** для офлайн-тестов.
- Индекс документов — готовый из Дня 21 (`day21/index/structure.json`); путь
  переопределяется env `INDEX_PATH`.
- Эмбеддинги — `paraphrase-multilingual-MiniLM-L12-v2` (как в Дне 21), копия
  модуля `embeddings.py`.

## Структура

```
day22/
  backend/
    .env / .env.example
    requirements.txt
    pyproject.toml
    app/
      main.py
      domain/models.py
      ports/llm_gateway.py        # протокол LLM.complete(messages) -> str
      ports/retriever.py          # протокол Retriever.search(question, top_k) -> [Hit]
      application/agent.py        # RAGAgent.answer(question, mode) -> Answer
      application/evaluator.py    # прогон 10 вопросов + оценка качества
      infrastructure/deepseek_gateway.py
      infrastructure/fake_llm.py
      infrastructure/retrieval.py
      infrastructure/embeddings.py
      infrastructure/settings.py
      presentation/routes.py
      presentation/schemas.py
      data/eval_questions.json
    tests/
      test_agent.py
      test_evaluator.py
      test_retrieval.py
      test_routes.py
  frontend/  (React + Vite)
    index.html
    package.json
    vite.config.js
    src/main.jsx
    src/App.jsx
    src/api.js
    src/styles.css
    src/components/QuestionInput.jsx
    src/components/AnswerPanel.jsx
    src/components/CompareTable.jsx
  README.md
  LESSON.md
  lesson.html
  video-script.html
```

## Доменные модели

- `Hit`: `chunk_id, source, title, section, score, text`.
- `Answer`: `mode` (`no_rag` | `rag`), `text`, `sources: list[Hit]` (пусто для no_rag).
- `Question`: `id, question, expectation, sources: list[str]` (подстроки ожидаемых файлов).
- `EvalItem`: `question, expectation, sources, no_rag_answer, no_rag_score,
  rag_answer, rag_score, rag_sources_used, source_coverage`.
- `EvalReport`: список `EvalItem` + `summary` (средний score обоих режимов,
  hit-rate источников, число вопросов).

## Поток данных

1. `no_rag`: `question -> LLM.complete([system?, user: question]) -> text`.
2. `rag`: `question -> retriever.search(question, top_k=4) -> контекст ->
   LLM.complete([system: инструкция отвечать по контексту, user: контекст + вопрос])
   -> text + sources`.

Промпты:

- `no_rag`: система «Ты — ассистент. Отвечай на вопрос кратко по своим знаниям.»,
  user = вопрос.
- `rag`: система «Ты — ассистент. Отвечай ТОЛЬКО по приведённому контексту,
  цитируй источник (секцию/файл). Если в контексте нет ответа — скажи об этом.»,
  user = контекст (чанки с заголовками) + вопрос.

## Retrieval

`retrieval.py` самостоятельно грузит JSON-индекс (`meta`, `chunks` с вложенным
`embedding`) и делает cosine-поиск через numpy, без копирования `chunking.py` /
`pipeline.py` из Дня 21. Использует копию `embeddings.py` для кодирования вопроса.
`top_k` по умолчанию 4 (переопределяется env `TOP_K`).

## 10 контрольных вопросов (KMP)

Темы (итоговый JSON в `data/eval_questions.json`): expect/actual, зависимости в
commonMain, иерархия source sets, публикация библиотеки, тестирование общего кода,
Ktor-клиент, Compose Multiplatform, поддержка iOS/Android, cinterop (нативные
библиотеки), kotlinx.serialization. У каждого — `question`, `expectation`,
`sources` (список подстрок, ожидаемых в найденных чанках).

## Оценка качества

Для каждого из 10 вопросов:

1. Ответ в обоих режимах.
2. **LLM-судья** (DeepSeek): оценка 0–1 каждого ответа против `expectation`
   (промпт судьи возвращает JSON с `score`). ~20 доп. вызовов.
3. **Покрытие источников**: пересечение `sources` вопроса с `source`/`section`
   найденных чанков (в режиме rag).

Итог: средний score «без RAG» vs «с RAG», hit-rate источников. Отчёт пишется в
`backend/data/eval_report.json` (кэш) и возвращается в API.

## API

- `POST /api/answer` — `{question}` → `{no_rag: Answer, rag: Answer}`.
- `POST /api/eval` — прогон 10 вопросов → `EvalReport` (кэшируется; повторный
  вызов отдаёт кэш, `?force=1` — пересчёт).
- `GET /api/questions` — список контрольных вопросов.

## Frontend (React + Vite)

- Поле ввода вопроса + кнопка «Спросить» → две панели рядом («без RAG» / «с RAG»),
  в панели RAG — список использованных источников.
- Вкладка «Сравнение по 10 вопросам» → таблица: вопрос, score без RAG, score с RAG,
  покрытие источников; сверху сводка (средние и hit-rate).

## Тестирование

FakeLLM (детерминированная: отвечает фиксированной строкой / эхо) и малый
fixture-индекс:

- `test_agent` — оба режима, подстановка контекста в prompt, источники.
- `test_retrieval` — загрузка индекса, top-k, порядок по скору.
- `test_evaluator` — структура отчёта, summary, кэш.
- `test_routes` — `/api/answer`, `/api/eval`, `/api/questions` (с FakeLLM).

Real-прогон — отдельной командой с DeepSeek (не в автотестах).

## Критерии готовности

- Агент отвечает в двух режимах; RAG-режим возвращает источники.
- 10 контрольных вопросов с ожиданиями и источниками зафиксированы.
- Отчёт сравнения (score + hit-rate) формируется и показывается в UI.
- Автотесты проходят офлайн (FakeLLM).
- README/LESSON/lesson.html/video-script.html заполнены; всё запушено в origin/main.
