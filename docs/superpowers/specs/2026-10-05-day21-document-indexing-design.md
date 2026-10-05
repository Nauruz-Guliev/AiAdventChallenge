# Day 21 — Индексация документов (chunking → embeddings → индекс)

## Цель

Построить **локальный пайплайн индексации** набора KMP-документов (Kotlin
Multiplatform), пригодный для дальнейшего использования в RAG:

1. **собрать** корпус актуальных KMP-документов (≥20–30 страниц текста);
2. **разбить** текст на чанки двумя стратегиями (chunking);
3. **сгенерировать** эмбеддинги для каждого чанка;
4. **сохранить** индекс с метаданными локально (JSON + numpy cosine-поиск);
5. **сравнить** две стратегии chunking по метрикам и качеству извлечения.

Итог — локальный индекс документов с эмбеддингами, метаданными и отчётом сравнения
двух стратегий. Отдельная страница `lesson.html` пошагово объясняет, что и как
сделано, чтобы проект можно было воспроизвести самостоятельно.

## Контекст

Тематика корпуса — **Kotlin Multiplatform (KMP)** по актуальным на сегодняшний день
источникам. Корпус собирается с web и складывается в `day21/corpus/*.md`:

- официальная документация kotlinlang.org (обзор KMP, структура проекта,
  expect/actual, целевые платформы, иерархия исходников, интеграция Swift/ObjC);
- JetBrains-блог и новости (стабилизация, roadmap);
- документация KMP-библиотек (Ktor client, kotlinx.serialization, Compose Multiplatform);
- книги/туториалы, в т.ч. русскоязычные.

Сбор документов — разовый шаг (скрипт + сохранённые `.md`); индексация и поиск —
офлайн-воспроизводимы.

## Вне-цели (YAGNI)

- Не строим полноценную LLM-чат-систему RAG — только **индексацию + поиск** по индексу.
- Не подключаем FAISS по умолчанию: дефолт — JSON + numpy (портируемо, инспектируемо,
  без нативных зависимостей на Windows). FAISS упомянут как альтернатива.
- Не поднимаем сервер/API/UI — только CLI (`pipeline.py`, `compare.py`, `query.py`).
- Не пишем свой токенизатор — используем токенизатор sentence-transformers; fallback —
  char-based, если модель недоступна.
- Нет автообновления корпуса; набор документов фиксируется на момент сборки.

## Ключевая идея

Классический конвейер индексации для RAG:

```
corpus/*.md
   │  load (по файлу, с title/section)
   ▼
chunking (стратегия A: fixed-size | стратегия B: structure)
   │  чанки + метаданные
   ▼
embeddings (sentence-transformers, батчинг, L2-normalize)
   │  embedding на чанк
   ▼
index (JSON: {chunk_id, source, title, section, strategy, text, embedding, meta})
   │
   ▼
search (numpy cosine top-k)  ──►  compare (A vs B)  ──►  query (CLI RAG-выборка)
```

Один и тот же корпус прогоняется через **обе** стратегии chunking независимо, поэтому
получаем два индекса и честное сравнение на одних данных.

### Две стратегии chunking

| | A: Fixed-size | B: Structure |
|---|---|---|
| Принцип | нарезка по ~512 токенов | по заголовкам `# → ## → ###` + границы файлов |
| Overlap | ~64 токена | нет (но секции склеиваются до min-размера) |
| `section` | `"fixed"` | путь заголовков (например `Введение > Платформы`) |
| Плюсы | равномерные чанки, простой | семантически цельные, сохраняют структуру |
| Минусы | режет по смыслу | неравномерные размеры |

Токенизация — через токенизатор модели; при отсутствии модели — по символам
(детерминированный fallback).

### Метаданные чанка

`source` (файл), `title` (заголовок документа), `section` (путь/`"fixed"`),
`chunk_id`, `strategy`, `char_offset`, `token_count`.

## Архитектура

### Дерево `day21/`

```
day21/
  corpus/                 # собранные KMP-документы (.md) — источник текста
  fetch_docs.py           # (разовый) сбор корпуса с web → corpus/*.md
  chunking.py             # chunk_fixed / chunk_structure + count_tokens
  embeddings.py           # SentenceTransformerEmbedder (батчинг, normalize)
  index.py                # IndexStore: build/save/load + cosine_search top-k
  pipeline.py             # end-to-end: corpus → chunks → embed → index (CLI)
  compare.py              # сравнение A vs B → markdown + JSON отчёт
  query.py                # CLI семантического поиска по индексу
  tests/test_chunking.py  # офлайн-тесты chunking (fake tokenizer)
  tests/test_index.py     # офлайн-тесты индекса (fake embedder)
  requirements.txt        # sentence-transformers, numpy, pytest
  pyproject.toml
  .gitignore              # .venv/, __pycache__/, .pytest_cache/, index/, video-script.html
  README.md
  LESSON.md               # конспект урока
  lesson.html             # подробный урок «сделай сам» (браузер)
  video-script.html       # сценарий видео (gitignored)
  index/                  # сгенерированные индексы (gitignored)
docs/superpowers/specs/2026-10-05-day21-document-indexing-design.md   # этот документ
```

### `chunking.py`

- `count_tokens(text, tokenizer=None) -> int` — токенизатор модели или char-fallback.
- `chunk_fixed(text, chunk_size=512, overlap=64, tokenizer=None) -> list[Chunk]` —
  по токенам; `section="fixed"`; `char_offset`/`token_count` на чанк; `chunk_id`
  вида `{source}:fixed:{i}`.
- `chunk_structure(markdown, min_tokens=128, tokenizer=None) -> list[Chunk]` — сплит
  по строкам-заголовкам (`^#{1,6}\s`); путь заголовков → `section`; мелкие секции
  склеиваются с соседними до `min_tokens`; `chunk_id` вида `{source}:struct:{i}`.
- `Chunk` — dataclass с полями метаданных; `as_dict()` для сериализации.
- Инварианты: нет пустых чанков, `chunk_id` уникальны, текст ненулевой.

### `embeddings.py`

- `SentenceTransformerEmbedder(model_name, batch_size=16)` — ленивая загрузка модели
  при первом использовании; `embed(texts) -> np.ndarray` (float32, L2-normalized).
- `FakeEmbedder(dim=64, seed=0)` — детерминированный (hashing по тексту) для тестов
  и для демонстрации пайплайна без скачивания модели.
- Модель по умолчанию: `paraphrase-multilingual-MiniLM-L12-v2` (мультиязычный RU+EN).

### `index.py`

- `IndexStore.build(chunks, embedder, batch_size) -> IndexDoc` — эмбеддинги батчами.
- `save(path)` / `load(path)` — JSON-файл `{meta, chunks: [{..., embedding}]}`.
- `cosine_search(query_vec, top_k=5) -> list[Hit]` — numpy dot-product (векторы уже
  нормализованы); `Hit = {chunk_id, source, title, section, score, text}`.
- Пути: `day21/index/{strategy}.json`.

### `pipeline.py` (CLI)

```
python pipeline.py --strategy fixed|structure|both [--embedder sentence|fake] [--chunk-size ...]
```

Загружает корпус → chunking → эмбеддинги → сохраняет индекс; печатает сводку
(число документов/чанков/токенов). `both` — прогоняет обе стратегии.

### `compare.py` (CLI)

Считает по каждой стратегии: число чанков, средний/мин/макс размер (токены),
дисперсию, перекрытие (для fixed), покрытие заголовков (для structure). Затем
**качество извлечения**: 5 контрольных запросов → top-3 по каждой стратегии →
попадание ожидаемого `source`/`section`. Вывод: markdown-таблица + JSON-отчёт в
`day21/index/comparison.md` / `.json`.

### `query.py` (CLI)

`python query.py "как устроен expect/actual" --strategy structure --top 5` — грузит
индекс, эмбеддит запрос, возвращает top-k чанков с метаданными и скором (RAG-выборка).

## Модель данных

Индекс-файл `day21/index/{strategy}.json`:

```json
{
  "meta": {"strategy": "structure", "model": "...", "embedding_dim": 384,
           "num_chunks": 120, "created_at": "..."},
  "chunks": [
    {"chunk_id": "overview:struct:3", "source": "overview.md",
     "title": "Kotlin Multiplatform overview", "section": "Get started",
     "strategy": "structure", "text": "...", "char_offset": 4123,
     "token_count": 214, "embedding": [0.01, -0.02, ...]}
  ]
}
```

## Тесты (офлайн, детерминированно) — ориентир ≥14

- `test_chunking.py` (fake tokenizer = по словам/символам):
  - `chunk_fixed`: нет пустых; overlap корректен; суммарное покрытие ~ всё;
    `chunk_id` уникальны и начинаются с `source`.
  - `chunk_structure`: сплит по заголовкам; `section` = путь; склейка мелких;
    границы файлов.
  - `count_tokens` char-fallback.
- `test_index.py` (FakeEmbedder):
  - build → save → load roundtrip (чанки, метаданные, эмбеддинги совпадают);
  - метаданные присутствуют у каждого чанка (source/title/section/chunk_id/strategy);
  - `cosine_search`: для тривиальных векторов правильный top-1;
  - `pipeline` с фейковым эмбеддером строит индекс по обоим стратегиям;
  - `compare` выдаёт отчёт по обеим стратегиям.

Запуск: `& ".venv\Scripts\python.exe" -m pytest -q`.

## Демонстрация (видео)

1. Показать `corpus/` — набор KMP-документов (≥20–30 стр.).
2. Запустить `pipeline.py --strategy both --embedder fake` (быстро, офлайн) →
   два индекса; затем реальную модель (`sentence`) на одном примере.
3. Показать фрагмент `index/structure.json` — чанк с метаданными и эмбеддингом.
4. `compare.py` → markdown-таблица: fixed vs structure (размеры, дисперсия, качество).
5. `query.py "…"` → top-3 чанка с метаданными и скором.
6. `pytest -q` → все зелёные.
7. Открыть `lesson.html` — подробный разбор с шагами «сделай сам».

## Критерии готовности

- [ ] Корпус `day21/corpus/*.md` (≥20–30 страниц KMP-текста) собран.
- [ ] `chunking.py`, `embeddings.py`, `index.py`, `pipeline.py`, `compare.py`, `query.py`.
- [ ] Две стратегии chunking + метаданные (source/title/section/chunk_id/strategy).
- [ ] Индексы сохранены в `day21/index/` (JSON + numpy).
- [ ] Отчёт сравнения двух стратегий (markdown + JSON).
- [ ] `pytest -q` зелёный (офлайн, fake embedder).
- [ ] `README.md`, `LESSON.md`, **`lesson.html` (подробный «сделай сам»)**,
      `video-script.html`.
- [ ] Коммит и push в `origin/main`.

## Риски и заметки

- `sentence-transformers`/`torch` — тяжёлая установка на Windows (~2 ГБ) и скачивание
  модели (~470 МБ) при первом запуске. Поэтому пайплайн и тесты умеют работать с
  `FakeEmbedder` — воспроизводимо без сети.
- Web-источники меняются: корпус фиксируем как файлы `.md` в репозитории, чтобы
  индексация была детерминированной.
- Мультиязычная модель хуже узкоспециализированных английских на чисто EN-тексте —
  осознанный компромисс ради RU-запросов.
- Кириллица: CLI-вывод через `$env:PYTHONIOENCODING="utf-8"`.
