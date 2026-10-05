# Day 21 — Индексация документов (Kotlin Multiplatform)

Локальный **пайплайн индексации** набора KMP-документов для RAG:
**chunking (2 стратегии) → эмбеддинги → JSON-индекс с метаданными → сравнение
стратегий → семантический поиск**.

Тема корпуса — **Kotlin Multiplatform**: официальная документация, README ключевых
библиотек и русскоязычные доки (144 документа, ≈1000 страниц текста).

## Идея

```
corpus/*.md
   │  load (source, title, text)
   ▼
chunking ──┬── fixed-size   (~512 токенов, overlap 64)
           └── structure    (по заголовкам # → ## → ###)
   │  чанки + метаданные
   ▼
embeddings (sentence-transformers, батчами, L2-normalize)
   │  вектор на чанк
   ▼
index (JSON: chunk_id, source, title, section, strategy, text, embedding, …)
   │
   ├─► compare.py  — сравнение двух стратегий (метрики + качество извлечения)
   └─► query.py    — семантический поиск top-k (RAG-выборка)
```

Один и тот же корпус независимо прогоняется через **обе** стратегии chunking, поэтому
сравнение честное — на одних данных.

## Структура

```
day21/
  corpus/                 # KMP-документы (.md): kmp-docs/ (122), libs/ (14), ru/ (8)
  fetch_docs.py           # сбор корпуса из GitHub raw (официальные доки + README + ru)
  SOURCES.md              # описание источников корпуса
  chunking.py             # Chunk, count_tokens, chunk_fixed, chunk_structure
  embeddings.py           # Embedder: SentenceTransformerEmbedder + FakeEmbedder
  index.py                # IndexStore: build / save / load / cosine-search
  pipeline.py             # CLI: corpus → chunks → embeddings → index
  compare.py              # CLI: сравнение fixed vs structure → comparison.md/.json
  query.py                # CLI: семантический поиск по индексу
  tests/                  # 25 офлайн-тестов (FakeEmbedder, без модели)
  requirements.txt        # sentence-transformers, numpy, pytest
  README.md
  LESSON.md               # конспект урока
  lesson.html             # подробный разбор «сделай сам» (браузер)
  video-script.html       # сценарий видео (в .gitignore)
  index/                  # сгенерированные индексы (в .gitignore)
```

## Две стратегии chunking

| | `fixed` | `structure` |
|---|---|---|
| Принцип | нарезка по ~512 токенов | по заголовкам markdown + границы файлов |
| Перекрытие | ~64 токена | нет (мелкие секции склеиваются до `min_tokens`) |
| `section` | `"fixed"` | путь заголовков, напр. `Project setup > Source sets` |
| Плюсы | равномерные чанки, предсказуемый размер | цельные по смыслу, сохраняют структуру документа |
| Минусы | режет предложения/секции | неравномерные размеры |

Реализация: `chunking.py:35` (`chunk_fixed`), `chunking.py:117` (`chunk_structure`).

## Метаданные чанка

Каждый чанк несёт:

| Поле | Смысл |
|---|---|
| `source` | относительный путь файла, напр. `kmp-docs/071-…-expect-actual.md` |
| `title` | заголовок документа |
| `section` | путь заголовков (`structure`) или `"fixed"` |
| `chunk_id` | `{source}:{strategy}:{i}` — уникальный |
| `strategy` | `fixed` или `structure` |
| `char_offset` | позиция начала чанка в документе |
| `token_count` | длина в токенах |

## Установка

```powershell
python -m venv .venv
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org
```

## Быстрый старт (офлайн, без модели)

`FakeEmbedder` даёт детерминированные, но **не семантические** векторы — удобно, чтобы
проверить пайплайн без скачивания модели:

```powershell
& ".venv\Scripts\python.exe" pipeline.py --strategy both --embedder fake
```

Пример вывода:

```
ВНИМАНИЕ: используется FakeEmbedder — векторы не семантические.
[fixed] chunks=506 tokens=225419 -> index\fixed.json
[structure] chunks=926 tokens=202251 -> index\structure.json
```

## Реальный индекс (semantic)

```powershell
& ".venv\Scripts\python.exe" pipeline.py --strategy both --embedder sentence
```

При первом запуске скачается модель `paraphrase-multilingual-MiniLM-L12-v2` (~470 МБ).
Дальше всё офлайн.

## Сравнение стратегий

```powershell
& ".venv\Scripts\python.exe" compare.py --embedder sentence
```

Пишет `index/comparison.md` и `index/comparison.json`: число чанков, средний/мин/макс
размер, дисперсия и **hit-rate** на 5 контрольных KMP-запросах (попадание ожидаемого
документа в top-3).

## Семантический поиск (RAG-выборка)

```powershell
& ".venv\Scripts\python.exe" query.py "how do expect and actual declarations work" --top 3
```

Пример:

```
1. [0.6173] kmp-docs/071-development-multiplatform-expect-actual.md :: Expected and actual declarations
   Expected and actual declarations allow you to access platform-specific APIs…
```

С кодом RAG это выглядит так: `query.py:answer()` возвращает top-k чанков с
метаданными — их тексты подставляются в промпт LLM.

## Тесты

```powershell
& ".venv\Scripts\python.exe" -m pytest -q
```

Ожидаемо: `25 passed`. Тесты полностью офлайн: `FakeEmbedder` (без модели),
временные индексы на `tmp_path`, проверка chunking, roundtrip save/load, cosine-поиск,
сборка пайплайна по обеим стратегиям.

## Использование как библиотеки

```python
from embeddings import get_embedder
from index import IndexStore

embedder = get_embedder("sentence")
store = IndexStore.load("index/structure.json")
hits = store.search_text("Ktor client in common code", embedder, top_k=5)
for h in hits:
    print(h.score, h.source, h.section)
```

## Материалы

- [`LESSON.md`](./LESSON.md) — конспект: chunking, эмбеддинги, индекс, сравнение.
- [`lesson.html`](./lesson.html) — подробный урок с шагами «повтори сам» (браузер).
- [`SOURCES.md`](./SOURCES.md) — откуда собран корпус.
