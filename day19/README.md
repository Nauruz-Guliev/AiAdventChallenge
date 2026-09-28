# Day 19 — Композиция MCP-инструментов

MCP-сервер **`compose`** из четырёх инструментов, которые складываются в
автоматический пайплайн: **`search`** (данные) → **`summarize`** (обработка) →
**`save_to_file`** (сохранение), плюс составной **`pipeline`**, который выполняет
всю цепочку сам и возвращает отчёт о передаче данных между этапами.

## Идея

День 17 дал один инструмент, день 18 — инструмент с фоновой работой. Здесь —
**композиция**: несколько маленьких инструментов с явными входами/выходами
(dict) объединяются в цепочку. Выход одного этапа — вход следующего:

```
search(query) ──{results}──► summarize(text) ──{summary}──► save_to_file(content) ──{path}
      └──── pipeline(query, path) вызывает все три сам и возвращает отчёт ────┘
```

## Структура

```
day19/
  search_api.py           # search(query, limit) → Wikipedia (без ключа)
  summarizer.py           # summarize(text, n) → экстрактивная суммаризация (офлайн)
  storage.py              # save_to_file(content, path) → файл + метаданные
  pipeline.py             # run(query, path) → search→summarize→save + отчёт
  server.py               # MCP-сервер "compose": 4 инструмента
  test_compose.py         # 18 офлайн-тестов (модули + pipeline + stdio)
  requirements.txt        # mcp>=2,<3 ; pytest>=8
  pyproject.toml
  opencode.example.jsonc  # образец конфига → скопировать в корень как opencode.json
  README.md
  LESSON.md               # конспект урока
  lesson.html             # подробный урок (браузер)
  video-script.html       # сценарий видео (в .gitignore)
  out/                    # результаты pipeline (в .gitignore)
```

## Инструменты

| Инструмент | Параметры | Возврат |
|---|---|---|
| `search` | `query: str`, `limit: int = 5` (1..10) | `{query, results: [{title, url, snippet}]}` |
| `summarize` | `text: str`, `sentences: int = 3` (1..10) | `{summary, original_chars, summary_chars, sentence_count}` |
| `save_to_file` | `content: str`, `path: str \| None` | `{path, bytes_written, written_at}` |
| `pipeline` | `query: str`, `path: str \| None`, `sentences: int = 3` | `{query, stages, output_path, summary}` |

В opencode инструменты видны с префиксом сервера: `compose_search`,
`compose_summarize`, `compose_save_to_file`, `compose_pipeline`.

## Источник данных

Поиск — **Wikipedia Search API** (`action=query&list=search`) на русском, без
ключа. Сниппеты приходят с HTML-разметкой (`<span class="searchmatch">…</span>`),
её чистит `_strip_html`. Суммаризация — **локальная экстрактивная**: частотность
значимых слов → топ предложений в исходном порядке (без внешнего LLM-ключа).

## Установка

```powershell
python -m venv .venv
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org
```

## Быстрая проверка

```powershell
$env:PYTHONIOENCODING="utf-8"; [Console]::OutputEncoding=[System.Text.Encoding]::UTF8
& ".venv\Scripts\python.exe" -c "import json, pipeline; print(json.dumps(pipeline.run('Model Context Protocol'), ensure_ascii=False, indent=2))"
```

Пишет файл в `day19/out/` и печатает отчёт со стадиями `search`/`summarize`/`save`.

## Подключение к opencode (только этот репозиторий)

1. Скопируй образец в корень репозитория:

   ```powershell
   Copy-Item day19\opencode.example.jsonc opencode.json
   ```

2. **Перезапусти opencode** (конфиг читается один раз при старте).

3. В чате:

   ```
   Найди в Википедии про Model Context Protocol и сохрани конспект в day19/out/
   ```

   Агент вызовет `compose_pipeline` и вернёт отчёт + путь к файлу.

**Важно:** проектный `opencode.json` действует, когда opencode запущен **из корня
репозитория** (тогда `cwd: "day19"` разрешается). Из другой папки используй
**глобальный** конфиг с абсолютными путями к `server.py` и `cwd`.

**Симптом ошибки:** `opencode mcp list` → `✗ compose failed` с
`ENOENT … uv_spawn 'uv'` — значит несуществующий рабочий каталог (относительный
`cwd` посчитан от чужой папки запуска). Лечится абсолютным `cwd` или запуском
opencode из корня репозитория.

## Тесты

```powershell
& ".venv\Scripts\python.exe" -m pytest -q
```

Ожидаемо: `18 passed`. Тесты офлайн: суммаризация (порядок/усечение/пустота),
запись файла (`tmp_path`), поиск (мокнутый `_get_json`), пайплайн (мок search,
временный файл) и stdio-интеграция (4 инструмента + схемы).

## Материалы

- [`LESSON.md`](./LESSON.md) — конспект: композиция и передача данных.
- [`lesson.html`](./lesson.html) — подробный урок (открой в браузере).
