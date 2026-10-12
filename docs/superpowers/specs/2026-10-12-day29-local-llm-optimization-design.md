# Day 29 — Оптимизация локальной LLM под RAG по KMP (дизайн)

## Цель

Превратить Telegram-бота дня 28 (RAG по базе KMP на локальной `gemma4:12b`) в **оптимизированную
под конкретную задачу** версию и показать в чате сравнение **до/после** по качеству, скорости и
потреблению ресурсов. Дополнительно — починить вывод в Telegram (markdown сейчас не рисуется).

## Целевая задача

**RAG-ответы по базе Kotlin Multiplatform** (та же задача, что в дне 28): на вход — вопрос и
найденный контекст, на выход — краткий ответ со ссылками `[n]` на источники. Поиск (retrieval) не
меняем — оптимизируем именно генерацию (параметры, квант, промпт), чтобы вклад был изолирован.

## Non-goals

- Не меняем retrieve-пайплайн (индекс дня 21, эмбеддер, реранк, top_k).
- Не обучаем/не файнтюним модель (только инференс-параметры и промпт).
- Не делаем мультимодельный роутинг (только Q4_K_M и Q8_0 одной модели).
- Не трогаем облачную ветку как объект оптимизации (DeepSeek используется только как судья и в `/eval`).

## Архитектура

`day29/backend/` — **форк** модулей дня 28 (по конвенции репозитория: day28 форкал day27/day25).
Добавляется слой оптимизации и чинится рендер.

```
day29/
  README.md  LESSON.md  lesson.html  video-script.html
  backend/
    requirements.txt  pyproject.toml  .gitignore  .env.example  run_bot.ps1  stop_bot.ps1
    app/
      main.py                      # сборка контейнера, polling
      config.py                    # + Q8-модель, дефолтный профиль/квант, лимиты A/B
      domain/models.py             # + OptimizationProfile, Quant, CellResult, ABReport, ResourceSample
      ports/llm.py                 # complete/stream_chat принимают model=
      infrastructure/
        ollama_client.py           # + model= override, prompt_eval_count, /api/ps, show
        resources.py               # сэмплер RSS/CPU процесса Ollama + /api/ps (psutil)
        embeddings.py              # из day28
        retrieval.py               # из day28
        heuristic_reranker.py      # из day28
        chat_store.py              # из day28
        telegram_net.py            # из day28
        deepseek_gateway.py        # из day28
      application/
        prompt.py                  # PROMPTS: baseline, optimized; build_context/build_messages
        optimization/
          __init__.py
          profiles.py              # PROFILES (baseline/params/optimized) + QUANTS (q4/q8)
          ab_runner.py             # матрица прогонов, агрегация метрик, дельты
        rag_service.py             # принимает профиль (options+prompt+think+model)
        citation.py                # из day28
        judge_deepseek.py          # из day28
        benchmark.py               # из day28 (локально vs облако, /eval)
        formatter.py               # ПОЧИНЕННЫЙ Telegram-рендер
      presentation/
        handlers.py                # команды, кнопки, /ab, /profile, /quant
        keyboards.py               # inline-кнопки
        messages.py                # тексты + рендер отчётов (Telegram-friendly)
        streamer.py                # стриминг с HTML-рендером
        middlewares.py             # из day28
    tests/                         # офлайн-тесты
    data/eval_questions.json       # из day22 (10 KMP-вопросов)
```

## Профили и параметры

`think=false` во всех профилях (как в дне 28).

| Профиль | label | num_ctx | temperature | top_p | top_k | num_predict | repeat_penalty | Промпт |
|---|---|---|---|---|---|---|---|---|
| `baseline` | Базовая (день 28) | 8192 | — (дефолт модели ≈1.0) | — (0.95) | — (64) | — (без лимита) | — | `baseline` |
| `params` | +Параметры | 4096 | 0.2 | 0.9 | 40 | 512 | 1.1 | `baseline` |
| `optimized` | +Промпт | 4096 | 0.2 | 0.9 | 40 | 512 | 1.1 | `optimized` |

- `baseline.options == {"num_ctx": 8192}` — ровно как `Settings.ollama_options()` дня 28.
- `params`/`optimized.options` — словарь выше (без `num_ctx`-дефолтов модели).
- **Safety (anti-truncation):** перед прогоном для каждого вопроса считается `prompt_tokens`; если
  `prompt_tokens + num_predict > num_ctx`, ячейка перезапускается с `num_ctx=6144` (фиксируется в
  метаданных отчёта флагом `ctx_bumped=true`). Это защита от обрезания контекста при маленьком окне.

### Кванты

```python
QUANTS = {
    "q4": Quant(name="q4", model="gemma4:12b",            label="Q4_K_M", size_gb_hint=8.0),
    "q8": Quant(name="q8", model="gemma4:12b-it-q8_0",    label="Q8_0",   size_gb_hint=13.0),
}
```

`q4` уже установлен; `q8` скачивается `ollama pull gemma4:12b-it-q8_0` (~13 ГБ, свободно ~21 ГБ).

## Промпты

`PROMPTS = {"baseline": <текст дня 28>, "optimized": <новый текст>}`.

**baseline** (переносится из `day28/app/application/prompt.py` без изменений):

> Ты — ассистент по Kotlin Multiplatform. Отвечай на русском, опираясь на КОНТЕКСТ (выдержки из
> документации). Каждый факт помечай ссылкой [n], где n — номер блока контекста. Не ссылайся на
> блоки, которые не используешь. Если в контексте нет ответа — честно скажи, что не нашёл, и не
> выдумывай.

**optimized:**

> Ты — справочный ассистент по Kotlin Multiplatform. Отвечай только по КОНТЕКСТУ.
> 1) Кратко: 2–5 пунктов или короткий абзац, без вступлений и повторения вопроса.
> 2) Каждый факт помечай ссылкой [n] на блок контекста.
> 3) Не используй знания вне контекста, не выдумывай.
> 4) Если ответа в контексте нет — ответь ровно: «Не нашёл в базе».
> 5) Язык — русский; имена API и код — как в контексте.

`build_messages(history, context, question, prompt_key)` выбирает system-промпт по ключу.
`build_context` — без изменений (нумерованные блоки `[n] source :: section`).

## Матрица экспериментов

3 профиля × 2 кванта = **6 ячеек**.

- **Quick** (`/ab`): 3 вопроса × 1 прогон (~2 мин).
- **Full** (`/ab full`): 10 вопросов × 2 прогона (~15–30 мин).

Вопросы берутся из `app/data/eval_questions.json` (10 контрольных KMP-вопросов, есть `expectation`).
Ретрив выполняется **один раз на вопрос** и переиспользуется между ячейками (честное сравнение).

### Метрики на ячейку

- **Качество**: слепой судья `DeepSeekJudge` (0…1 по `expectation`, не знает модель/профиль/квант);
  mean и std по всем прогонам ячейки.
- **Скорость**: латентность (mean/std, мс) и tok/s (`eval_count / eval_duration`), mean.
- **Токены промпта**: `prompt_eval_count`, mean.
- **Ошибки**: доля неудачных генераций (таймаут/ошибка Ollama).
- **Ресурсы** (`ResourceSample`): `model_size_gb` (диск), `size_vram_gb` (`/api/ps`), `rss_peak_mb`
  (пик RSS процесса Ollama), `cpu_percent` (средний CPU процесса Ollama за генерации),
  `load_ms` (`load_duration` первого ответа в ячейке).

### Модели данных

```python
@dataclass(frozen=True)
class OptimizationProfile:
    name: str; label: str; options: dict; prompt: str; think: bool = False

@dataclass(frozen=True)
class Quant:
    name: str; model: str; label: str; size_gb_hint: float

@dataclass(frozen=True)
class ResourceSample:
    model_size_gb: float; size_vram_gb: float; rss_peak_mb: float
    cpu_percent: float; load_ms: float

@dataclass(frozen=True)
class CellResult:
    profile: str; quant: str; label: str
    quality_mean: float; quality_std: float
    latency_mean_ms: float; latency_std_ms: float
    tokens_per_second: float; prompt_tokens: float
    error_rate: float; runs: int; ctx_bumped: bool
    resources: ResourceSample

@dataclass(frozen=True)
class ABReport:
    cells: tuple[CellResult, ...]; questions: int; runs: int; quick: bool
```

### Замер ресурсов (`resources.py`)

- `find_ollama_process()` — процесс `ollama`/`ollama app` через `psutil`.
- `ResourceSampler` — фоновая задача, каждые `resource_sample_interval` (0.5 c) читает RSS и CPU
  процесса; копит пик RSS и сумму CPU.
- `ollama_ps(client)` — `GET /api/ps` → `size_vram`.
- `model_size_gb(client, model)` — `GET /api/tags` (или `ollama show`) → размер модели.
- Всё оборачивается в try/except: если процесс не найден, ресурсы по памяти = 0 и в отчёт
  добавляется строка-примечание.

## Telegram UX

### Команды

| Команда | Действие |
|---|---|
| `/start`, `/help` | приветствие/справка (с учётом новых команд) |
| `/profile` | показать активный профиль и его параметры |
| `/profile baseline\|params\|optimized` | переключить активный профиль для обычных ответов |
| `/quant q4\|q8` | переключить квант; показать размер модели и память |
| `/ab` | быстрый A/B: 3 вопроса × 1 |
| `/ab full` | полный A/B: 10 вопросов × 2, с прогрессом |
| `/eval` | локально vs облако (как в дне 28) |
| `/status` | модель, квант, профиль, индекс, RAG, облако, память |
| `/rag`, `/norag`, `/think on\|off` | как в дне 28 |
| `/new`, `/reset`, `/id` | как в дне 28 |

### Кнопки под ответом

`⚙️ Профиль` (`profile`) · `📊 A/B` (`ab`) · `🔀 Квант` (`quant`) · `🔄 RAG: вкл/выкл`
(`toggle_rag`) · `☁️ Облако` (`cloud`). `⚙️ Профиль` и `🔀 Квант` переключают одним нажатием
(циклически по списку) и отвечают `query.answer(...)`, обновляя подпись.

### Обычный ответ бота

Идёт по **активному профилю** (по умолчанию `optimized`) и активному кванту. Стримится, рендерится
в HTML, под ответом — блок «📚 Источники» и кнопки. Переключение профиля/кванта сразу меняет
поведение → живое «до/после»: `/profile baseline` → ответ хуже/длиннее; `/profile optimized` → короче.

### Рендер отчётов (Telegram-friendly)

- **Без markdown-таблиц.** Таблицы выводятся как моноширинные `<pre>`-блоки с выравниванием
  (Telegram `<pre>` — monospace).
- Пример `/ab`:
  ```
  📊 A/B: RAG по KMP · 10 вопросов × 2 · Q4_K_M

  профиль        кач-во   латентн.  tok/s   ток.промп  память
  Базовая         0.79     3480 мс    109      1980     8.4 ГБ
  +Параметры      0.83     2600 мс    128      1975     5.1 ГБ
  +Промпт         0.87     2400 мс    133      1970     5.1 ГБ

  Δ (оптим. vs базовая): качество +0.08 · латентность −1080 мс
  Судья: deepseek-chat, оценка слепая.
  ```
- Дельты считаются от `baseline` того же кванта.
- Короткие строки, bold-заголовки, `<pre>` для чисел.
- **Отчёты собираются в `messages.py` сразу как валидный HTML** (числа экранированы), шлются через
  `split_message` с `parse_mode="HTML"` и **не** прогоняются повторно через `md_to_telegram_html`
  (чтобы не съесть `<pre>`). Конвертер markdown применяется только к выводу модели.

## Фикс рендера (formatter.py)

**Причина баги:** `md_to_telegram_html` оборачивает абзацы в `<p>` и использует `<br>`, а Telegram
HTML их не поддерживает → `edit_text(parse_mode="HTML")` падает → `except` глотает ошибку →
сообщение остаётся сырым. Плюс во время стриминга правки идут без `parse_mode`, а путь
переполнения (`_emit_parts`) отправляет raw-текст.

**Новый конвертер `md_to_telegram_html(text) -> str`** — только поддерживаемые теги
(`<b> <i> <u> <s> <code> <pre> <a href>`), никаких `<p>`/`<br>`:

1. Экранировать `& < >`.
2. Блоки ```` ```lang\n...\n``` ```` → `<pre><code>…</code></pre>` (сначала, «заглушками»).
3. Инлайн `` `code` `` → `<code>…</code>`.
4. `**bold**` / `__bold__` → `<b>`; `*italic*` / `_italic_` → `<i>`; `~~strike~~` → `<s>`.
5. Ссылки `[текст](url)` → `<a href="url">текст</a>` (url экранируется).
6. Заголовки `#…######` (в начале строки) → `<b>текст</b>`.
7. Списки `-`/`*`/`+` в начале строки → `• `; `1.` оставляем.
8. Абзацы — пустой строкой `\n\n`, строки — `\n`. (Не `<p>`, не `<br>`.)
9. Восстановить заглушки кода.

**Стриминг-safe:** при каждой правке конвертируется **текущий** буфер; конвертер всегда возвращает
валидный HTML (незакрытые маркеры трактуются буквально), а `_close_and_carry` в `split_message`
закрывает/переносит теги при нарезке. Ошибка Telegram при правке по-прежнему перехватывается
(фолбэк на предыдущий текст), но валидный HTML делает её маловероятной.

**Стриминг рендерит HTML:** `TelegramMessageStreamer._render` вызывает `md_to_telegram_html(buffer)`
и редактирует с `parse_mode="HTML"`; `start()` шлёт плейсхолдер; `finish()` — HTML + футер;
`_emit_parts` (переполнение) конвертирует каждый кусок и шлёт с `parse_mode="HTML"`.

**Бэкпорт:** та же функция(и) переносится в `day28/backend/app/application/formatter.py` (и, при
необходимости, `streamer.py`), чтобы текущий бот дня 28 тоже рисовал markdown. Тесты дня 28
(`test_formatter.py`) обновляются/дополняются, весь набор остаётся зелёным.

## Конфиг (дополнения `Settings`)

```
ollama_model_q8: str = "gemma4:12b-it-q8_0"
default_profile: str = "optimized"     # baseline | params | optimized
default_quant: str = "q4"              # q4 | q8
ab_quick_questions: int = 3
ab_full_questions: int = 10
ab_runs: int = 2
resource_sample_interval: float = 0.5
```

`requirements.txt` дополняется `psutil>=5.9,<7`.

## Тестирование (офлайн, без сети)

- `test_formatter_telegram.py`: нет `<p>`/`<br>`; экранирование `&<>`; жирный/курсив/зачёркнутый/
  код/блок кода/ссылка/заголовок; маркеры внутри кода не форматируются; частичный ввод даёт
  валидный HTML; `split_message` не рвёт теги.
- `test_profiles.py`: реестр профилей и квантов; `baseline.options == {"num_ctx": 8192}`;
  `optimized` использует `optimized`-промпт; merge options.
- `test_ab_runner.py`: агрегация качества/скорости, дельты от baseline, `ctx_bumped`, обработка
  ошибок и отсутствия судьи; фейковые LLM/судья/сэмплер ресурсов.
- `test_resources.py`: фейковый psutil-процесс → пик RSS и CPU; отсутствие процесса → нули + флаг.
- `test_ollama_client_model.py`: `complete(model=...)`/`stream_chat(model=...)` подставляют модель в
  payload; парсинг `prompt_eval_count`, `load_duration`.
- `test_rag_service_profile.py`: профиль применяется (options + промпт + model).
- `test_keyboards.py`, `test_handlers_smoke.py`: кнопки и сборка роутера.

## Документация

- `day29/README.md` — что, как запускать, команды, методология A/B, **таблица реальных результатов**
  (заполняется после живого прогона).
- `day29/LESSON.md` — конспект: что меняем и почему (параметры, квант, промпт), как читать метрики,
  почему retrieval фиксирован.
- `day29/lesson.html`, `day29/video-script.html`.
- Строка про day29 в корневом `README.md`.

## Риски и решения

- **Q8 (~13 ГБ, свободно ~21 ГБ)** — качаем один раз; если загрузка недоступна, отчёт помечает
  квант q8 как недоступный и матрица сокращается до q4 (деградация, но не падение).
- **Память Q8** при загрузке выше Q4 — фиксируем RSS/`size_vram`, это и есть часть результата.
- **Судья недоступен (нет ключа/сети)** — `/ab` показывает скорость/ресурсы, качество = «—».
- **Долгий полный A/B** — выполняется фоновой задачей с прогрессом; повторный `/ab` в чате
  блокируется локом; есть быстрый режим.
- **Один токен с днём 28** — бот дня 29 вытесняет день 28 (запускать по одному).

## Критерии готовности

1. `day29` собирается, `pytest` зелёный (офлайн).
2. Бот запускается на `@AiAdventNauruzBot`; markdown и таблицы **рисуются** аккуратно.
3. `/profile baseline → optimized` меняет ответ вживую; `/quant q4 → q8` переключает модель и
   показывает размер/память.
4. `/ab` и `/ab full` выводят таблицу качества/скорости/ресурсов с дельтами.
5. README содержит реальные цифры до/после (качество, скорость, ресурсы) и вклад кванта.
6. Доки (README/LESSON/lesson.html/video-script) и строка в корневом README.

## Решения по брейншторму

- Целевая задача — RAG-ответы по KMP (день 28).
- Квантование — реально скачать и сравнить Q8_0 против Q4_K_M.
- Формат — отдельная папка `day29` со своим (доработанным) ботом, вытесняющим день 28.
- Матрица — абляции (baseline → params → optimized) × 2 кванта.
- UX — профиль + A/B + переключатель кванта.
- Ресурсы — метрики Ollama + память и CPU.
- Режимы A/B — быстрый и полный.
