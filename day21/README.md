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
chunking ──┬── fixed-size   (~120 токенов, overlap 20)
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
  tests/                  # 28 офлайн-тестов (FakeEmbedder, без модели)
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
| Принцип | окна по ~120 токенов | по заголовкам markdown + границы файлов |
| Перекрытие | ~20 токенов | нет (мелкие секции склеиваются до `min_tokens`) |
| `section` | `"fixed"` | путь заголовков, напр. `Project setup > Source sets` |
| Плюсы | равномерные чанки, предсказуемый размер | цельные по смыслу, сохраняют структуру документа |
| Минусы | режет предложения/секции | неравномерные размеры |

Размер чанка ограничен `max_seq_length=128` модели эмбеддингов: более длинные чанки
обрезались бы при эмбеддинге, поэтому окно по умолчанию — 120 токенов (реальные токены
модели, не слова). Секции в `structure` длиннее лимита дополнительно режутся на окна.

Реализация: `chunking.py` — `chunk_fixed`, `chunk_structure`.

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

## Как запускать команды (важно)

Все команды выполняются **в PowerShell из папки `day21`**, а Python-скрипты
запускаются **только через интерпретатор из venv**. Иначе PowerShell не распознаёт
`query.py` как команду, а системный `python` не видит установленные зависимости.

```powershell
cd day21
$env:PYTHONIOENCODING="utf-8"; [Console]::OutputEncoding=[System.Text.Encoding]::UTF8

& ".venv\Scripts\python.exe" query.py "how do expect and actual declarations work" --top 3
```

> `query.py "..."` сам по себе в PowerShell **не сработает** — это файл, а не команда.
> Всегда используйте префикс `& ".venv\Scripts\python.exe"` (или, если venv активирован,
> короткий вариант `python query.py ...`).

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
[fixed] chunks=2070 tokens=240771 -> index\fixed.json
[structure] chunks=2294 tokens=202251 -> index\structure.json
```

(Числа зависят от токенизатора: на реальной модели-токенизаторе чанков больше —
см. раздел «Результаты».)

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

### Результаты реального прогона

| Метрика | fixed | structure |
|---|---|---|
| num_chunks | 4942 | 4817 |
| total_tokens | 585339 | 489379 |
| avg_tokens | 118.44 | 101.59 |
| min_tokens | 21 | 1 |
| max_tokens | 120 | 120 |
| std_tokens | 10.26 | 33.31 |
| **hit_rate** | **0.8** | **0.6** |

`fixed` даёт ровные чанки (std 10.26 против 33.31) и выше качество извлечения на этом
наборе запросов; `structure` — чанки-секции с осмысленным `section`, но с «хвостами»
в 1 токен.

## Семантический поиск (RAG-выборка)

```powershell
& ".venv\Scripts\python.exe" query.py "how do expect and actual declarations work" --top 3
```

Пример:

```
1. [0.7390] kmp-docs/071-development-multiplatform-expect-actual.md
   :: Expected and actual declarations > Rules for expected and actual declarations
   ## Rules for expected and actual declarations  To define expected and actual declarations…
2. [0.6442] kmp-docs/068-development-multiplatform-connect-to-apis.md
   :: Use platform-specific APIs > … > Further reading on `expect`/`actual` declarations
```

С кодом RAG это выглядит так: `query.py:answer()` возвращает top-k чанков с
метаданными — их тексты подставляются в промпт LLM.

## Тесты

```powershell
& ".venv\Scripts\python.exe" -m pytest -q
```

Ожидаемо: `28 passed`. Тесты полностью офлайн: `FakeEmbedder` (без модели),
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
