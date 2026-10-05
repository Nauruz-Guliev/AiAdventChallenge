# День 22 — Первый RAG-запрос

Агент отвечает на вопрос двумя способами и показывает разницу:

- **без RAG** — вопрос напрямую в LLM (только собственные знания модели);
- **с RAG** — вопрос → поиск релевантных чанков в индексе Дня 21 → контекст + вопрос → LLM, с указанием источников.

Плюс **10 контрольных вопросов** и **сравнение качества** (оценка ответов LLM-судьёй).

Стек: FastAPI (backend) + React/Vite (frontend), LLM — DeepSeek API.

## Как это работает

```
вопрос ──► (no_rag) ─────────────────────────► LLM ──► ответ
       └─► (rag) retrieval top-k ► контекст ──► LLM ──► ответ + источники
```

- Индекс берётся готовый из Дня 21: `day21/index/structure.json` (4817 чанков).
- Эмбеддинги вопроса — `paraphrase-multilingual-MiniLM-L12-v2` (как в Дне 21).
- Судья (LLM) оценивает каждый ответ 0…1 на соответствие ожиданию.

## Структура

```
day22/
  backend/   FastAPI: agent, evaluator, retrieval, DeepSeek gateway (+ FakeLLM)
  frontend/  React: ввод вопроса, два ответа рядом, таблица сравнения
```

## Установка и запуск

Все команды — в PowerShell. Backend и frontend запускаются в двух окнах.

### 1. Backend

```powershell
cd day22/backend
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
cd day22/frontend
npm install
npm run dev
```

Открой http://localhost:5173 — вкладка «Вопрос» (два ответа рядом) и «Сравнение по 10 вопросам».

### Офлайн-режим (без ключа)

В `.env` поставь `LLM_PROVIDER=fake` — ответы будет давать детерминированная заглушка (удобно проверить интерфейс без API).

## API

| Метод | Путь | Что делает |
|---|---|---|
| POST | `/api/answer` | `{question}` → оба ответа (no_rag и rag + источники) |
| GET | `/api/questions` | список 10 контрольных вопросов |
| POST | `/api/eval` | прогон 10 вопросов + оценка, пишет `data/eval_report.json` (кэш; `?force=1` — пересчёт) |

## 10 контрольных вопросов

Темы: expect/actual, зависимости в commonMain, иерархия source sets, публикация в Maven, тесты, Ktor, навигация в Compose MP, поддерживаемые платформы, CocoaPods/iOS, kotlinx.serialization. У каждого — ожидание и ожидаемые источники (`app/data/eval_questions.json`).

## Результаты реального прогона

Средние по 10 вопросам (DeepSeek-судья, 0…1):

| Метрика | Значение |
|---|---|
| Средний балл без RAG | **0.98** |
| Средний балл с RAG | **0.74** |
| Покрытие источников (RAG) | **0.80** |

Вывод: сама модель знает KMP хорошо, поэтому «без RAG» сильна. RAG добавляет
**опору на конкретную документацию и ссылки на источники**, но её качество
ограничено retrieval: маленькие чанки и англоязычные доки при русском вопросе
иногда не дают полного ответа. Это наглядно показывает главный тезис RAG:
**качество RAG = качество поиска**.

## Тесты

```powershell
cd day22/backend
& .venv/Scripts/python.exe -m pytest -q
```

Все тесты офлайн (FakeLLM + фикстурный индекс).
