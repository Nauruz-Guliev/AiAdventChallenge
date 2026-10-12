# День 28 — Telegram RAG-бот на локальной LLM + сравнение с облаком

Статус: утверждён к реализации.

## 1. Цель

Telegram-бот, который отвечает на вопросы по базе знаний Kotlin Multiplatform через
**RAG, полностью локально**:

- **retrieval** — локальные эмбеддинги (`paraphrase-multilingual-MiniLM-L12-v2`) по
  готовому индексу Недели 6 (`day21/index/structure.json`, 4817 чанков);
- **generation** — локальная модель (`gemma4:12b` через Ollama);
- ответ сопровождается **источниками** (и цитатами, если модель их дала).

Дополнительно прямо в чате можно запустить **сравнение с облачной моделью** (DeepSeek) и
получить отчёт по **качеству / скорости / стабильности** — то есть «выполнить задание»
не выходя из Telegram.

## 2. Рамки и не-цели

**В рамках:**

- Telegram-бот (aiogram 3, long polling) с RAG-пайплайном Недели 6.
- Локальная генерация + локальный retrieval по умолчанию.
- Команды и inline-кнопки для переключения режима, сравнения и прогона оценки.
- Отчёт `/eval` приходит **в чат** (файлы на диск не пишутся). Итоговые цифры после
  реального прогона вносятся в `README.md`/`LESSON.md`.

**Вне рамок (YAGNI):**

- Фото/vision, аудио, инструменты, MCP.
- Веб-фронтенд, FastAPI-сервер.
- Память задачи (task memory) и сценарии из Дня 25.
- Сохранение отчёта в файл/репозиторий (по решению — только чат).

## 3. Ключевые решения

| Вопрос | Решение |
|---|---|
| Форма результата | Telegram-бот (+ сравнение в чате) |
| Токен | тот же, что в Дне 27 (`@AiAdventNauruzBot`); День 27 останавливается при запуске Дня 28 |
| Код | новая папка `day28/` (переиспользует модули Дней 21/25/27) |
| Функции бота | стриминг, история диалога, команды, источники, `/norag`; без vision |
| Индекс | `day21/index/structure.json` (путь в конфиге) |
| Локальная модель | `gemma4:12b` (Ollama) |
| Облачная модель и судья | DeepSeek (`deepseek-chat`), ключ переиспользуется из `day25/backend/.env` |
| Судья | слепая оценка 0…1 по единой рубрике (без подписи модели) |
| Строки `/eval` | Локальная+RAG, Облако+RAG, Локальная без RAG |
| Объём `/eval` | 10 вопросов × 3 прогона (по умолчанию); `/eval N` меняет число прогонов |
| Отчёт | только в чат (без `report.md`) |
| Thinking (gemma) | по умолчанию **выключен** для RAG/эвала; `/think` включает |

## 4. Архитектура

Чистая архитектура (domain → ports → infrastructure → application → presentation),
как в Днях 25 и 27. Папка `day28/backend/`.

```
app/
  domain/models.py          # Hit, Source, RagAnswer, ChatMessage, GenerationStats,
                            # EvalQuestion, EvalRow, EvalReport, ошибки
  ports/
    retriever.py            # Retriever: search(question, top_k), similarity(text, chunk_id)
    llm.py                  # StreamingLLM: stream_chat(...)  (локальная)
                            # LLM: complete(messages) -> str   (локальная и облачная)
    judge.py                # Judge: score(question, context, answer) -> Score
  infrastructure/
    embeddings.py           # [day25] SentenceTransformerEmbedder + FakeEmbedder
    retrieval.py            # [day25] JsonRetriever (numpy cosine по индексу)
    heuristic_reranker.py   # [day25] HeuristicReranker + filter_by_threshold
    ollama_client.py        # [day27] stream_chat + new complete(); health(); list_models()
    deepseek_gateway.py     # [new] complete() через openai AsyncOpenAI
    chat_store.py           # [day27] JSON-история по чату
    telegram_net.py         # [day27] обход блокировки TG (резолв api.telegram.org)
    config.py               # [day27] + RAG/облако/эвал-настройки
  application/
    prompt.py               # [new] системный промпт + сборка контекста [n] + история
    rag_service.py          # [new] retrieve → rerank → filter → gating → generate → источники
    citation.py             # [day25] маркеры [n] + LCS-цитаты
    benchmark.py            # [new] прогон 10×N×3 строк, агрегация метрик
    judge_deepseek.py       # [new] слепой судья
    formatter.py            # [day27] markdown→HTML, безопасный сплит 4096
  presentation/
    handlers.py             # [day27] + /rag //norag /compare /eval /think /status
    keyboards.py            # [new] inline-кнопки
    streamer.py             # [day27] троттлинг edit_message_text
    middlewares.py          # [day27] ErrorMiddleware
    messages.py             # [day27] тексты команд/справки
  main.py                   # запуск: config → override IP → health → polling (resilient)
tests/                      # офлайн-тесты
data/                       # история чатов (gitignore)
requirements.txt  .env.example  run_bot.ps1  stop_bot.ps1
```

Переиспользование: файлы помечены `[dayNN]` копируются/адаптируются из
соответствующих дней (в репозитории это принятая практика — День 25 так наследует День 24).

## 5. Поток данных (RAG-ответ)

```
сообщение пользователя
  └─ если режим RAG (по умолчанию):
       1. embed(вопрос)                                      # локально
       2. retriever.search(top_k_pre=30)                     # локально
       3. reranker.rerank + filter_by_threshold(min_sim=0.35, k_post=6)
       4. gating: relevance = cos(вопрос, лучший чанк)
            если relevance < NO_ANSWER_MIN_SCORE (0.60) → «Не нашёл в базе» (answerable=false)
       5. prompt = system + история(chat_store) + контекст[n] + вопрос
       6. stream через Ollama (think=false) → правки сообщения (троттлинг ~1.2 c)
       7. финал: ответ + блок «Источники» [n] source :: section (score)
                  [+ «Цитаты», если извлечены маркерами [n] и LCS]
  └─ если режим /norag:
       свободный ответ модели без retrieval (для контраста)
```

**При `/compare` и `/eval` контекст ищется один раз** и подаётся одинаково локальной и
облачной модели — сравнивается именно генерация, а не разный retrieval.

В историю диалога сохраняются только текст пользователя и текст ответа (без блока
«Источники»/«Цитаты»), чтобы не раздувать контекст. В режиме `/norag` источников нет.

## 6. Бот: команды и кнопки

Команды:

| Команда | Действие |
|---|---|
| `/start`, `/help` | приветствие/справка |
| `/new`, `/reset` | очистить историю диалога |
| `/rag` | включить retrieval (по умолчанию включён) |
| `/norag` | выключить retrieval (свободный ответ модели) |
| `/compare <вопрос>` | ответ локальной и облачной модели рядом + время каждой |
| `/eval [N]` | прогон оценки (по умолчанию N=3), отчёт в чат |
| `/think` | вкл/выкл thinking у локальной модели |
| `/status` | состояние: Ollama, индекс, эмбеддер, режим RAG, облако |
| `/id` | id чата |

Inline-кнопки под ответом:

- **☁️ Облако** — тот же вопрос и контекст через DeepSeek;
- **⚖️ Сравнить** — оба ответа рядом + время;
- **🧪 Прогон 10 вопросов** — запускает `/eval`;
- **🔄 RAG вкл/выкл** — тумблер режима.

Последний вопрос и найденный контекст на чат хранятся в состоянии, чтобы кнопки
отрабатывали без повторного ввода. Только приватные чаты.

## 7. `/eval`: качество, скорость, стабильность

- **Вопросы**: 10 контрольных KMP-вопросов из `day22/backend/app/data/eval_questions.json`
  (копируются в `day28`).
- **Прогоны**: `EVAL_RUNS=3` по умолчанию (`/eval N` переопределяет).
- **Строки**: Локальная+RAG, Облако+RAG, Локальная без RAG.
- **Методика**: на каждый (вопрос, прогон): retrieval один раз → идентичный промпт →
  генерация тремя способами (локальная+RAG, облачная+RAG, локальная без RAG).
- **Качество**: судья DeepSeek, слепая оценка 0…1 по единой рубрике; судья не знает,
  какая модель дала ответ. Итог — среднее по вопросам и прогонам.
- **Скорость**: средняя латентность (мс); для локальной — tok/s из статистики Ollama
  (`eval_count`/`eval_duration`).
- **Стабильность**: std балла и латентности по прогонам + доля ошибок/таймаутов.
- **Ход**: одно редактируемое сообщение-прогресс («вопрос 3/10, прогон 2/3…»).
- **Финал**: таблица в чат (при необходимости делится на части) + 3–5 выводов.
- В одном чате одновременно допускается один `/eval`; повторный запуск отклоняется.

Ожидаемое время: ~60 локальных генераций 12B (при ~126 tok/s из Дня 27 — несколько
минут) + облачные вызовы параллельно.

## 8. Конфигурация (`.env`)

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | тот же токен, что в Дне 27 |
| `TELEGRAM_API_IP` | `149.154.167.220` | обход блокировки TG в этой сети |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama |
| `OLLAMA_MODEL` | `gemma4:12b` | локальная модель |
| `OLLAMA_NUM_CTX` | `8192` | контекст |
| `OLLAMA_KEEP_ALIVE` | `10m` | удержание модели |
| `THINK_DEFAULT` | `false` | thinking по умолчанию |
| `INDEX_PATH` | `../../day21/index/structure.json` | индекс Недели 6 |
| `EMBEDDER` | `sentence` | `sentence` \| `fake` |
| `EMBEDDER_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | модель эмбеддингов |
| `TOP_K_PRE` | `30` | top-k до фильтра |
| `TOP_K_POST` | `6` | top-k в контекст |
| `MIN_SIM` | `0.35` | cosine-порог фильтра |
| `NO_ANSWER_MIN_SCORE` | `0.60` | порог «не знаю» |
| `DEEPSEEK_API_KEY` | — | облако/судья (из `day25/backend/.env`) |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com/v1` | DeepSeek |
| `DEEPSEEK_MODEL` | `deepseek-chat` | облачная модель и судья |
| `EVAL_RUNS` | `3` | прогонов на вопрос |
| `EVAL_QUESTIONS_PATH` | `app/data/eval_questions.json` | контрольные вопросы |
| `HISTORY_MAX_MESSAGES` / `HISTORY_MAX_CHARS` | `20` / `12000` | ограничение истории |
| `DATA_DIR` | `data` | история чатов |
| `REQUEST_TIMEOUT` | `300` | таймаут запросов к LLM |

При старте: проверка токена, health Ollama, наличие индекса, наличие ключа DeepSeek
(облачные функции деградируют мягко, если ключа нет).

Индекс должен быть собран **той же** моделью эмбеддингов (`paraphrase-multilingual-MiniLM-L12-v2`,
размерность 384). При несовпадении размерности/модели — предупреждение в лог и `/status`.

## 9. Тестирование

Офлайн, без сети и без реальных моделей:

- `FakeEmbedder` + маленький фикстурный JSON-индекс;
- `FakeLLM` (реализует и `stream`, и `complete`); `FakeJudge`;
- `httpx.MockTransport` для клиентов Ollama и DeepSeek.

Покрытие: retrieval/rerank/filter, gating и сборка промпта, извлечение источников и
цитат, агрегация бенчмарка и парсинг оценки судьи, formatter (сплит/HTML), chat_store,
config, telegram_net, smoke хендлеров.

## 10. Документы и видео

`day28/README.md`, `day28/LESSON.md`, `day28/lesson.html`, `day28/video-script.html`
(в стиле Дня 27), строка в корневом `README.md`. Реальные цифры прогона вносятся в
README/LESSON после проверки.

## 11. Риски и меры

| Риск | Мера |
|---|---|
| Сеть избирательно блокирует Telegram | `TELEGRAM_API_IP` + resilient polling (из Дня 27) |
| Один токен с Днём 27 | перед запуском Дня 28 остановить День 27 |
| Долгий `/eval` блокирует бота | фоновая задача + прогресс; один прогон на чат |
| Память/VRAM: эмбеддер + 12B одновременно | задокументировать требования |
| Индекс/модель отсутствуют | `/status` и понятная ошибка при старте |
| Облако недоступно/нет ключа | локальный RAG работает независимо; облачные команды сообщают об ошибке |

## 12. Критерии приёмки

1. Обычное сообщение в боте → локальный RAG-ответ со стримингом и источниками.
2. `/norag` → ответ без retrieval; `/rag` возвращает.
3. `/compare <вопрос>` → два ответа рядом + время.
4. `/eval` → таблица качество/скорость/стабильность по трём строкам, отчёт в чат.
5. Вся локальная цепочка (эмбеддинги + генерация) работает без облака; облако только
   для сравнения/судьи.
6. Офлайн-тесты зелёные.
7. `README.md`, `LESSON.md`, `lesson.html`, `video-script.html` готовы; корневой README
   обновлён.
