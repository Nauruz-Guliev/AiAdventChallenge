# Day 19 — Композиция MCP-инструментов (пайплайн)

## Цель

Сделать несколько MCP-инструментов, которые **композируются в пайплайн**:

1. **`search`** — получает данные (Wikipedia);
2. **`summarize`** — обрабатывает данные (локальная экстрактивная суммаризация);
3. **`save_to_file`** — сохраняет результат на диск.

Плюс составной инструмент **`pipeline`**, который сам выполняет цепочку
`search → summarize → save_to_file` и возвращает отчёт о передаче данных между
этапами. Демонстрация: агент одной фразой запускает весь пайплайн и получает
готовый файл-конспект, а также может вызвать каждый инструмент по отдельности.

## Вне-цели (YAGNI)

- Без внешних LLM-ключей и платных API: суммаризация — **локальная и
  детерминированная** (частотность слов → выбор предложений).
- Только один источник поиска — **Wikipedia** (REST, без ключа). Без DuckDuckGo,
  без локального поиска по репозиторию.
- Только stdio-транспорт; без HTTP/SSE-сервера.
- Без фонового демона (это был день 18) — здесь всё синхронно по вызову.
- Без UI, без конфигов сложнее `opencode.example.jsonc`.
- Не трогаем глобальный конфиг; подключение **проектное** (`opencode.json` в корне).
- Не пишем собственный агент — агентом выступает opencode.

## Ключевая идея: композиция через явные типы данных

Каждый инструмент — отдельная чистая функция с понятным входом и выходом (dict).
Пайплайн — это композиция функций: выход одного этапа становится входом следующего.
«Корректность передачи данных» проверяется тем, что:

- `search` возвращает список результатов → из них строится текст;
- `summarize` принимает текст → возвращает `summary` + метрики;
- `save_to_file` принимает контент → пишет файл и возвращает путь;
- `pipeline` собирает всё это в один отчёт, где виден каждый этап и его результат.

## Архитектура

```
opencode (агент)
   │  stdio / JSON-RPC
   ▼
day19/server.py   (MCP: search, summarize, save_to_file, pipeline)
   │
   ├─ search_api.py   →  Wikipedia (network)
   ├─ summarizer.py   →  extractive (чистая функция)
   ├─ storage.py      →  запись файла (ФС)
   └─ pipeline.py     →  композиция трёх выше + отчёт
```

### Дерево `day19/`

```
day19/
  search_api.py           # search(query, limit) → Wikipedia
  summarizer.py           # summarize(text, n) → экстрактивная суммаризация
  storage.py              # save_to_file(content, path) → файл + метаданные
  pipeline.py             # run(query, path) → search→summarize→save + отчёт
  server.py               # MCP-сервер "compose": 4 инструмента
  test_compose.py         # pytest: модули + pipeline + stdio (офлайн)
  requirements.txt        # mcp>=2,<3 ; pytest>=8
  pyproject.toml          # pythonpath=., testpaths=.
  .gitignore              # .venv/, __pycache__/, .pytest_cache/, out/, video-script.html
  opencode.example.jsonc  # образец проектного конфига для копирования в корень
  README.md
  LESSON.md
  lesson.html
  video-script.html
docs/superpowers/specs/2026-09-28-day19-composition-design.md   # этот документ
opencode.json             # (в корне, создаёт пользователь) регистрация compose
```

### `search_api.py` — получение данных

- `search(query: str, limit: int = 5) -> dict` с полями
  `{query, results: [{title, url, snippet}]}`.
- Источник — Wikipedia Search API:
  `https://ru.wikipedia.org/w/api.php?action=query&list=search&format=json&srsearch=<q>&srlimit=<n>&srprop=snippet&formatversion=2`.
- `snippet` содержит HTML-разметку `<span class="searchmatch">…</span>` — чистим
  теги до текста (`_strip_html`).
- Ошибки сети/пустой ответ → `SearchError` (обёртка над `urllib.error.URLError` и
  `ValueError`), которую `server.py` превращает в `ValueError` (→ `isError` в MCP).
- `limit` клампится в `1..10`.

### `summarizer.py` — обработка

- `summarize(text: str, sentences: int = 3) -> dict` с полями
  `{summary, original_chars, summary_chars, sentence_count}`.
- Алгоритм (детерминированный, офлайн):
  1. разбить на предложения по `[.!?…]` (+ перевод строки);
  2. построить частотность «значимых» слов (длина ≥ 3, без стоп-слов RU);
  3. оценить каждое предложение суммой частот его слов, поделить на длину
     (нормировка против длинных предложений);
  4. вернуть топ-N предложений **в исходном порядке** (не в порядке оценки);
  5. если предложений меньше N — вернуть все.
- Пустой текст → `{summary: "", ...}` без ошибки (граничный случай).
- Чистая функция: не зависит от сети/ФС, легко тестируется.

### `storage.py` — сохранение

- `save_to_file(content: str, path: str | None = None) -> dict` с полями
  `{path, bytes_written, written_at}`.
- `path` по умолчанию: `day19/out/<epoch>-<slug>.md`, где slug — из `query`/заголовка
  (передаёт pipeline). Папка `out/` создаётся при необходимости.
- `storage.save_to_file` пишет `content` **как есть** в UTF-8; заголовок и структуру
  markdown собирает `pipeline` (разделение обязанностей: storage = только запись).
- Ошибка пути/прав → `StorageError` → в MCP превращается в `ValueError`.
- Путь нормализуется через `Path(...).resolve()`, чтобы в отчёте был абсолютный путь.

### `pipeline.py` — композиция

- `run(query: str, path: str | None = None, sentences: int = 3) -> dict`:

  1. `search(query)` → `results`;
  2. собрать текст: заголовок + первые `N` сниппетов;
  3. `summarize(text, sentences)` → `summary`;
  4. собрать финальный markdown (`# query`, источники-ссылки, `## Summary`,
     саммари);
  5. `save_to_file(final_md, path)` → `path`;
  6. вернуть отчёт:

  ```json
  {
    "query": "...",
    "stages": {
      "search": {"result_count": 5, "top_titles": ["...", ...]},
      "summarize": {"sentence_count": 3, "summary_chars": 412},
      "save": {"path": "C:/.../out/....md", "bytes_written": 1004}
    },
    "output_path": "C:/.../out/....md",
    "summary": "текст саммари"
  }
  ```

- Это и есть «автоматическое выполнение цепочки»: один вызов → все три этапа + их
  результаты в одном ответе. «Корректность передачи» видна по полям `stages`.

### `server.py` — MCP-обёртка

`MCPServer("compose")`. Инструменты (возврат `dict`; доменные ошибки → `ValueError`):

| Инструмент | Параметры | Возврат |
|---|---|---|
| `search` | `query: str`, `limit: int = 5` | `{query, results}` |
| `summarize` | `text: str`, `sentences: int = 3` | `{summary, original_chars, summary_chars, sentence_count}` |
| `save_to_file` | `content: str`, `path: str \| None = None` | `{path, bytes_written, written_at}` |
| `pipeline` | `query: str`, `path: str \| None = None`, `sentences: int = 3` | отчёт (см. выше) |

Имя сервера в opencode префиксует инструменты: `compose_search`,
`compose_summarize`, `compose_save_to_file`, `compose_pipeline`.

## Модель данных

Постоянной БД нет. Всё состояние — внутри одного вызова. Единственное «постоянное»
— файл на диске в `day19/out/`. Это сознательно проще, чем день 18: фокус на
композиции функций, а не на хранении.

## Конфигурация и пути

- `day19/out/` — каталог результатов, **в `.gitignore`**.
- Тесты пишут только в `tmp_path` — реальный `out/` не задевается.
- `storage.py` резолвит `out/` относительно файла `storage.py` (как в дне 18 БД —
  относительно `scheduler.py`), чтобы не зависеть от cwd.

## Регистрация в opencode

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "compose": {
      "type": "local",
      "command": ["uv", "run", "--no-project", "--with", "mcp>=2,<3", "server.py"],
      "cwd": "day19",
      "enabled": true,
      "timeout": 60000
    }
  }
}
```

Примечание (из дня 18): проектный `opencode.json` работает, когда opencode запущен
**из корня репозитория**. Из другой папки — глобальный конфиг с **абсолютными**
путями к `server.py` и `cwd`.

## Тесты (офлайн, без сети) — ориентир ≥15

`test_compose.py`:

- `summarizer`: порядок (топ-предложения в исходном порядке), сокращение длины,
  пустой текст → пустой саммари, меньше предложений чем N → все.
- `storage`: запись в `tmp_path`, `bytes_written` = длина UTF-8, автосоздание папки,
  невалидный путь → `StorageError`.
- `search_api`: `_strip_html` чистит теги; `search` с мокнутым `_get_json` возвращает
  `{query, results}`; пустой ответ → `SearchError`; кламп `limit`.
- `pipeline`: с мокнутым `search_api.search` (без сети) `run` пишет файл в `tmp_path`
  и возвращает отчёт с корректными `stages` (передача данных).
- stdio-интеграция: `tools/list` содержит 4 инструмента; схемы `search` (required
  `query`), `pipeline`; вызов `summarize` через stdio возвращает текст.

Запуск: `& ".venv\Scripts\python.exe" -m pytest -q`.

## Демонстрация (видео)

1. `opencode mcp list` → `✓ compose connected`.
2. opencode: «Найди в Википедии про MCP и сохрани конспект» → агент вызывает
   `compose_pipeline("Model Context Protocol")` → отчёт с этапами + файл.
3. Показать содержимое `day19/out/*.md`.
4. Показать отдельные вызовы: `compose_search`, `compose_summarize`,
   `compose_save_to_file`.
5. `pytest -q` → все зелёные.

## Критерии готовности

- [ ] `search_api.py`, `summarizer.py`, `storage.py`, `pipeline.py`, `server.py`
      реализованы.
- [ ] `pytest -q` зелёный (офлайн).
- [ ] Живой `search` работает (Wikipedia), `pipeline` пишет файл.
- [ ] `day19/opencode.example.jsonc` регистрирует `compose`.
- [ ] В opencode агент вызывает инструменты (цепочка + по отдельности).
- [ ] Обновлены `README.md`, `LESSON.md`, `lesson.html`, `video-script.html`.
- [ ] Коммит и push в `origin/main`.

## Риски и заметки

- Wikipedia может медленно отвечать/блокироваться → `SearchError` → `ValueError`
  (агент видит ошибку, не падает).
- `snippet` возвращается с HTML-тегами — обязательная чистка `_strip_html`.
- Экстрактивная суммаризация не «понимает» текст — это осознанное упрощение
  (без LLM-ключа). Для конспекта сниппетов её достаточно.
- Кириллица: JSON-RPC в UTF-8; файлы пишем в UTF-8 с `newline` по умолчанию.
