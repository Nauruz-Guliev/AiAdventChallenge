# День 9: сжатие истории — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Агент с управляемым сжатием истории: rolling-summary + хвост из последних N сообщений вместо полной истории в запросе; тумблер в UI для сравнения качества и расхода токенов.

**Architecture:** Наследие day8 (FastAPI + React, pytest): полная история никогда не удаляется — `summary`/`summary_covers` кэшируются в чате, а параметр `compress` решает, что пойдёт в API: весь список (day8) или `[system-behavior + summary-system + KEEP_RECENT хвост]`. Чистые функции сборки контекста — в `application/compression.py`, оркестрация — в `Agent`, отчёт о сжатии летит во фронт через `usage.compression`.

**Tech Stack:** Python 3.12, FastAPI, tiktoken, pydantic v2, pytest/httpx (TestClient), React 19 + Vite, react-markdown.

**Spec:** `docs/superpowers/specs/2026-09-14-day9-context-compression-design.md`

## Global Constraints

- Все команды backend — **только из `day9/backend`** (Settings читает `.env` от cwd).
- `DEEPSEEK_API_KEY` только в gitignored `.env`; в коммиты — никогда.
- Реальный путь API: `/api/chats/...`, тело сообщения — `{"message": str}` (НЕ `/api/v1`, НЕ `content`).
- Модель отвечает на русском в UI; код, идентификаторы, коммиты — английский; коммиты conventional (`feat:/fix:/test:/docs:/chore:`).
- `CONTEXT_LIMIT_TOKENS=8000` остаётся жёстким бюджетом (413-страховка).
- Сжатие НЕ удаляет сообщения из хранилища.
- Frontend-тестов нет: верификация = `npm run build` + живой dev-сервер.

## Структура файлов (day9)

| Файл | Действие | Ответственность |
|---|---|---|
| `day9/backend/app/domain/models.py` | modify | `Chat.summary/summary_covers`, `CompressionInfo`, `UsageConfig.compress_*`, `UsageReport.compression` |
| `day9/backend/app/application/compression.py` | create | чистые функции: split/сборка summary-запросов |
| `day9/backend/app/application/usage.py` | modify | `summarization_cost_usd` |
| `day9/backend/app/application/ports/chat_repository.py` | modify | `save_summary` |
| `day9/backend/app/infrastructure/json_chat_repository.py` | modify | персист summary |
| `day9/backend/app/infrastructure/settings.py` | modify | 3 новые env-настройки |
| `day9/backend/app/presentation/dependencies.py` | modify | прокинуть настройки в UsageConfig |
| `day9/backend/app/application/agent.py` | modify | flow сжатия в `run(..., compress=True)` |
| `day9/backend/app/presentation/schemas.py` + `routes.py` | modify | `compress` в запросе, `usage.compression`, summary в GET |
| `day9/frontend/src/App.jsx` | modify | состояние тумблера, чип-данные |
| `day9/frontend/src/components/ChatPanel.jsx` | modify | тумблер + чип |
| `day9/frontend/src/api.js` | modify | `sendMessage(chatId, message, compress)` |
| тесты: `test_json_chat_repository.py`, новый `test_compression.py`, `test_usage.py`, `test_agent.py`, `test_chat_api.py` | modify/create | по задачам |

---

### Task 1: Скаффолд day9 из day8

**Files:**
- Create: `day9/` (копия `day8/` без артефактов)
- Modify: `day9/backend/pyproject.toml`, `day9/backend/app/main.py`, `day9/frontend/package.json`, `day9/frontend/src/App.jsx` (hero)

**Interfaces:**
- Produces: работающий day8-код под именем day9; pytest `46 passed`; `npm run build` ✓.

- [ ] **Step 1: Скомигать spec-fix (уже сделан в рабочей копии) и скопировать каркас**

```bash
cd /Users/nauruz/AIADVENTCHALLENGE
git add docs/superpowers/specs/2026-09-14-day9-context-compression-design.md
git commit -m "docs: align day9 spec with actual day8 API surface"
rsync -a --exclude .venv --exclude __pycache__ --exclude node_modules --exclude data --exclude .env --exclude dist day8/ day9/
```

- [ ] **Step 2: Переименования**

`day9/backend/pyproject.toml`: `name = "advent-challenge-day9-backend"`.
`day9/frontend/package.json`: `"name": "advent-challenge-day9-frontend"`.
`day9/backend/app/main.py`: заголовок приложения → `"Day 9 Context Compression"`.
`day9/frontend/src/App.jsx`: строка hero `DAY 08` → `DAY 09`, подпись дня — «Сжатие истории» (одно предложение рядом, где day8 писал про подсчёт токенов).

- [ ] **Step 3: Окружения**

```bash
cd day9/backend && python3 -m venv .venv && .venv/bin/pip install -q -e ".[dev]" && cp .env.example .env
cd ../frontend && npm install --no-audit --no-fund
```
В `.env` вручную вписать DEEPSEEK_API_KEY из `day8/backend/.env` (gitignored).

- [ ] **Step 4: Зеленый базис**

Run: `cd day9/backend && .venv/bin/pytest -q` → Expected: `46 passed`.
Run: `cd day9/frontend && npm run build` → Expected: `✓ built`.

- [ ] **Step 5: Commit**

```bash
git add day9
git commit -m "chore: scaffold day9 from day8"
```
(`day9/**/.venv`, `node_modules`, `.env`, `data/` не должны попасть — проверить `git status --short | grep day9 | grep -E "venv|node_modules|\.env$|data/"`, вывод пуст.)

---

### Task 2: Хранение summary (domain + repository)

**Files:**
- Modify: `day9/backend/app/domain/models.py` (dataclass `Chat`)
- Modify: `day9/backend/app/application/ports/chat_repository.py`
- Modify: `day9/backend/app/infrastructure/json_chat_repository.py`
- Test: `day9/backend/tests/test_json_chat_repository.py`

**Interfaces:**
- Consumes: day8 `Chat`, `JsonChatRepository`.
- Produces: `Chat.summary: str | None = None`, `Chat.summary_covers: int = 0`; `JsonChatRepository.save_summary(chat_id: str, summary: str, covers: int) -> Chat`; legacy-файлы без полей читаются с default'ами.

- [ ] **Step 1: Падающие тесты** — в конец `tests/test_json_chat_repository.py`:

```python
async def test_save_summary_round_trip(repository):
    chat = await repository.create_chat()
    updated = await repository.save_summary(chat.id, "Пользователь обсуждал X.", 4)
    assert updated.summary == "Пользователь обсуждал X."
    assert updated.summary_covers == 4
    loaded = await repository.get_chat(chat.id)
    assert loaded.summary == "Пользователь обсуждал X."
    assert loaded.summary_covers == 4


async def test_save_summary_missing_chat_raises(repository):
    with pytest.raises(ChatNotFound):
        await repository.save_summary("missing", "s", 1)


async def test_legacy_chat_without_summary_fields(tmp_path):
    path = tmp_path / "chats.json"
    path.write_text(json.dumps({"chats": [{
        "id": "legacy", "title": "T", "created_at": "x", "updated_at": "y",
        "messages": [],
    }]}, ensure_ascii=False))
    repo = JsonChatRepository(path)
    chat = await repo.get_chat("legacy")
    assert chat.summary is None
    assert chat.summary_covers == 0
```
В шапке файла добавить `import json` и `from app.domain.models import ChatNotFound` (если ещё не импортированы; фикстура `repository` в файле есть — проверить имя и использовать его).

- [ ] **Step 2: Прогон — FAIL**

Run: `cd day9/backend && .venv/bin/pytest tests/test_json_chat_repository.py -q`
Expected: `TypeError: __init__() got an unexpected keyword argument` или AttributeError.

- [ ] **Step 3: Реализация**

`domain/models.py` — в `Chat` (frozen dataclass) добавить поля с defaults:

```python
@dataclass(frozen=True)
class Chat:
    id: str
    title: str
    created_at: str
    updated_at: str
    messages: list[ChatMessage]
    summary: str | None = None
    summary_covers: int = 0
```

`ports/chat_repository.py` — в Protocol:

```python
    async def save_summary(
        self, chat_id: str, summary: str, covers: int
    ) -> Chat: ...
```

`json_chat_repository.py` — метод (style как `delete_chat`: лок, `_read_store`, запись) и хелперы:

```python
    async def save_summary(self, chat_id: str, summary: str, covers: int) -> Chat:
        async with self._lock:
            store = self._read_store()
            for stored_chat in store["chats"]:
                if stored_chat["id"] == chat_id:
                    stored_chat["summary"] = summary
                    stored_chat["summary_covers"] = covers
                    self._write_store(store)
                    return _chat_from_dict(stored_chat)
            raise ChatNotFound(chat_id)
```
`_chat_to_dict`: `+"summary": chat.summary, "summary_covers": chat.summary_covers`.
`_chat_from_dict`: `summary=stored_chat.get("summary"), summary_covers=stored_chat.get("summary_covers", 0)`.
В `append_exchange` конструкция возвращаемого Chat через `_chat_from_dict` уже сохранит summary, т.к. он лежит в stored-словаре.

- [ ] **Step 4: Прогон — PASS**

Run: `.venv/bin/pytest tests/test_json_chat_repository.py -q` → Expected: `all passed`.
Полный регресс: `.venv/bin/pytest -q` → Expected: `49 passed`.

- [ ] **Step 5: Commit** `git add day9/backend && git commit -m "feat: persist rolling summary in chat storage"`

---

### Task 3: Чистые функции сжатия + стоимость свёртки

**Files:**
- Create: `day9/backend/app/application/compression.py`
- Create: `day9/backend/tests/test_compression.py`
- Modify: `day9/backend/app/domain/models.py` (`CompressionInfo`, поля `UsageConfig`)
- Modify: `day9/backend/app/application/usage.py` (`summarization_cost_usd`)
- Test: `day9/backend/tests/test_usage.py`

**Interfaces:**
- Consumes: `ChatMessage`, `TokenUsage`, `UsageConfig`.
- Produces:
  - `split_history(messages: Sequence[ChatMessage], keep_recent: int) -> tuple[list[ChatMessage], list[ChatMessage]]`
  - `build_summarization_messages(summary: str | None, old_messages: Sequence[ChatMessage], max_tokens: int) -> list[ChatMessage]`
  - `build_summary_message(summary: str, covered: int) -> ChatMessage` (role `system`)
  - `CompressionInfo(applied, before_tokens, after_tokens, saved_tokens, saved_percent, summarization_tokens, summarization_cost_usd)`
  - `UsageConfig` += `compress_at_tokens: int = 3000`, `keep_recent_messages: int = 10`, `summary_max_tokens: int = 500`
  - `summarization_cost_usd(usage: TokenUsage, config: UsageConfig) -> float`

- [ ] **Step 1: Падающие тесты** — `tests/test_compression.py`:

```python
from app.application.compression import (
    build_summarization_messages,
    build_summary_message,
    split_history,
)
from app.domain.models import ChatMessage


def make_history(count: int) -> list[ChatMessage]:
    messages: list[ChatMessage] = []
    for index in range(count):
        messages.append(ChatMessage(role="user", content=f"вопрос {index}"))
        messages.append(ChatMessage(role="assistant", content=f"ответ {index}"))
    return messages


def test_split_history_keeps_recent_tail():
    history = make_history(8)  # 16 сообщений
    old, recent = split_history(history, keep_recent=10)
    assert len(recent) == 10
    assert recent == history[-10:]
    assert old == history[:-10]


def test_split_history_short_dialog_has_no_old_part():
    history = make_history(3)
    old, recent = split_history(history, keep_recent=10)
    assert old == []
    assert recent == history


def test_summarization_messages_shape():
    old = make_history(2)
    messages = build_summarization_messages("прошлая свёртка", old, max_tokens=500)
    assert messages[0].role == "system"
    assert messages[1].role == "user"
    assert "прошлая свёртка" in messages[1].content
    assert "вопрос 0" in messages[1].content
    assert "500" in messages[1].content


def test_summarization_messages_without_previous_summary():
    messages = build_summarization_messages(None, make_history(1), max_tokens=500)
    assert "нет" in messages[1].content


def test_build_summary_message():
    message = build_summary_message("Кратко: о X.", 12)
    assert message.role == "system"
    assert "12" in message.content
    assert "Кратко: о X." in message.content
```

дописать в `tests/test_usage.py`:

```python
def test_summarization_cost_usd():
    usage = TokenUsage(prompt_tokens=1_000_000, completion_tokens=500_000, total_tokens=1_500_000)
    config = UsageConfig()
    # 1M input по 0.30 + 0.5M output по 1.20 = 0.30 + 0.60
    assert summarization_cost_usd(usage, config) == pytest.approx(0.90)


def test_summarization_cost_zero_usage():
    assert summarization_cost_usd(TokenUsage(0, 0, 0), UsageConfig()) == 0.0
```
(+ импорт `summarization_cost_usd`, `UsageConfig`, `TokenUsage`, `pytest` — часть уже импортирована в файле.)

- [ ] **Step 2: FAIL** — `cd day9/backend && .venv/bin/pytest tests/test_compression.py tests/test_usage.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Реализация**

`app/application/compression.py`:

```python
from typing import Sequence

from app.domain.models import ChatMessage

SUMMARIZER_SYSTEM_PROMPT = (
    "You compress dialogue history into a terse, factual summary. "
    "Write in the same language as the dialogue. Preserve: the user's goals "
    "and constraints, established facts, decisions taken, open questions, "
    "exact names and numbers. No commentary, no invented details."
)


def split_history(
    messages: Sequence[ChatMessage], keep_recent: int
) -> tuple[list[ChatMessage], list[ChatMessage]]:
    if len(messages) <= keep_recent:
        return [], list(messages)
    return list(messages[:-keep_recent]), list(messages[-keep_recent:])


def build_summarization_messages(
    summary: str | None,
    old_messages: Sequence[ChatMessage],
    max_tokens: int,
) -> list[ChatMessage]:
    transcript = "\n".join(
        f"{message.role}: {message.content}" for message in old_messages
    )
    user_prompt = (
        f"Предыдущая свёртка диалога: {summary or 'нет'}.\n\n"
        f"Сообщения для сжатия:\n{transcript}\n\n"
        f"Обнови краткое содержание диалога, уложившись примерно в {max_tokens} токенов."
    )
    return [
        ChatMessage(role="system", content=SUMMARIZER_SYSTEM_PROMPT),
        ChatMessage(role="user", content=user_prompt),
    ]


def build_summary_message(summary: str, covered: int) -> ChatMessage:
    return ChatMessage(
        role="system",
        content=(
            f"Краткое содержание предыдущих {covered} сообщений диалога:\n{summary}"
        ),
    )
```

`domain/models.py` — `UsageConfig` дополнить (после существующих полей) и новый dataclass после `DialogUsage`:

```python
@dataclass(frozen=True)
class UsageConfig:
    context_limit_tokens: int = 8000
    input_price_per_million: float = 0.30
    output_price_per_million: float = 1.20
    compress_at_tokens: int = 3000
    keep_recent_messages: int = 10
    summary_max_tokens: int = 500


@dataclass(frozen=True)
class CompressionInfo:
    applied: bool
    before_tokens: int
    after_tokens: int
    saved_tokens: int
    saved_percent: int
    summarization_tokens: int
    summarization_cost_usd: float
```

`usage.py` — функция (использует уже имеющиеся `exchange_cost_usd`):

```python
def summarization_cost_usd(usage: TokenUsage, config: UsageConfig) -> float:
    return round(
        exchange_cost_usd(usage.prompt_tokens, usage.completion_tokens, config), 6
    )
```
(импорты `TokenUsage`/`UsageConfig` в usage.py уже есть из day8.)

- [ ] **Step 4: PASS + регресс** — `.venv/bin/pytest -q` → Expected: `56 passed`.

- [ ] **Step 5: Commit** `git commit -am "feat: add pure compression builders and summarization cost"` (файлы из `git add day9/backend`).

---

### Task 4: Flow сжатия в Agent

**Files:**
- Modify: `day9/backend/app/application/agent.py`
- Test: `day9/backend/tests/test_agent.py`

**Interfaces:**
- Consumes: `compression.*`, `summarization_cost_usd`, `Chat.summary/summary_covers`, `CompressionInfo`.
- Produces: `Agent.run(chat_id: str, user_text: str, compress: bool = True) -> AgentResult`; `AgentResult.usage.compression: CompressionInfo | None`; `UsageReport.history_tokens` = токены *отправленной* истории (после сжатия, если применялось).

- [ ] **Step 1: Падающие тесты** — дописать в `tests/test_agent.py`:

```python
class ScriptedGateway:
    """Отдаёт responses по порядку; пишет все вызовы в .calls."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def complete(self, messages):
        self.calls.append(messages)
        return self.responses.pop(0)


class CompressionRepository:
    def __init__(self, history):
        self.chat = Chat(
            id="chat-1",
            title="Т",
            created_at="2026-09-14T12:00:00+00:00",
            updated_at="2026-09-14T12:00:00+00:00",
            messages=list(history),
        )
        self.summaries = []

    async def get_chat(self, chat_id):
        return self.chat

    async def save_summary(self, chat_id, summary, covers):
        self.summaries.append((chat_id, summary, covers))
        self.chat = Chat(
            id=self.chat.id,
            title=self.chat.title,
            created_at=self.chat.created_at,
            updated_at=self.chat.updated_at,
            messages=self.chat.messages,
            summary=summary,
            summary_covers=covers,
        )
        return self.chat

    async def append_exchange(self, chat_id, user_content, assistant_content, usage):
        self.chat = Chat(
            id=self.chat.id,
            title=self.chat.title,
            created_at=self.chat.created_at,
            updated_at=self.chat.updated_at,
            messages=[
                *self.chat.messages,
                ChatMessage(role="user", content=user_content),
                ChatMessage(role="assistant", content=assistant_content, usage=usage),
            ],
            summary=self.chat.summary,
            summary_covers=self.chat.summary_covers,
        )
        return self.chat


def long_history(pairs=12):
    """12 пар по ~200 слов — больше COMPRESS_AT_TOKENS=3000 на русском."""
    filler = " " + "информация " * 40
    history = []
    for index in range(pairs):
        history.append(ChatMessage(role="user", content=f"вопрос {index}{filler}"))
        history.append(
            ChatMessage(role="assistant", content=f"ответ {index}{filler}")
        )
    return history


def compression_config():
    return UsageConfig(context_limit_tokens=20000)


def build_agent(gateway, repository, config=None):
    return Agent(
        gateway,
        repository=repository,
        counter=TiktokenCounter(),
        config=config or compression_config(),
        model="fake-model",
    )


@pytest.mark.asyncio
async def test_no_compression_below_threshold():
    repo = CompressionRepository([ChatMessage(role="user", content="короткий")])
    gateway = ScriptedGateway([sample_llm_response()])
    result = await build_agent(gateway, repo).run("chat-1", "ещё вопрос")
    assert result.usage.compression is None
    assert len(gateway.calls) == 1


@pytest.mark.asyncio
async def test_compression_sums_up_then_sends_tail():
    repo = CompressionRepository(long_history())
    summary_response = LLMResponse(
        "Итог: пользователь обсуждал информацию.", "fake-model",
        TokenUsage(prompt_tokens=9000, completion_tokens=100, total_tokens=9100),
    )
    answer_response = sample_llm_response()
    gateway = ScriptedGateway([summary_response, answer_response])

    result = await build_agent(gateway, repo).run("chat-1", "что я просил в начале?")

    assert len(gateway.calls) == 2
    summarization_call, main_call = gateway.calls
    assert summarization_call[0].role == "system"
    # основной запрос: system-поведение + summary-system + 10 хвостовых + новое сообщение
    assert main_call[0].content == SYSTEM_PROMPT
    assert main_call[1].role == "system" and "Итог:" in main_call[1].content
    assert len(main_call) == 1 + 1 + 10 + 1
    assert repo.summaries == [("chat-1", "Итог: пользователь обсуждал информацию.", 14)]
    compression = result.usage.compression
    assert compression.applied is True
    assert compression.before_tokens > compression.after_tokens
    assert compression.saved_tokens == compression.before_tokens - compression.after_tokens
    assert compression.summarization_tokens == 9100
    assert result.usage.history_tokens == compression.after_tokens


@pytest.mark.asyncio
async def test_compression_reuses_cached_summary():
    history = long_history()
    repo = CompressionRepository(history)
    repo.chat = Chat(
        id=repo.chat.id, title=repo.chat.title,
        created_at=repo.chat.created_at, updated_at=repo.chat.updated_at,
        messages=history,
        summary="готовая свёртка", summary_covers=14,
    )
    gateway = ScriptedGateway([sample_llm_response()])
    result = await build_agent(gateway, repo).run("chat-1", "продолжим")
    assert len(gateway.calls) == 1  # только основной вызов
    assert "готовая свёртка" in gateway.calls[0][1].content
    assert result.usage.compression.applied is True
    assert result.usage.compression.summarization_tokens == 0


@pytest.mark.asyncio
async def test_compress_disabled_sends_full_history():
    repo = CompressionRepository(long_history())
    gateway = ScriptedGateway([sample_llm_response()])
    result = await build_agent(gateway, repo).run("chat-1", "вопрос", compress=False)
    assert len(gateway.calls) == 1
    assert len(gateway.calls[0]) == 1 + 24 + 1  # system + полная история + новое
    assert result.usage.compression is None


@pytest.mark.asyncio
async def test_compression_cannot_rescue_giant_tail():
    huge = [
        ChatMessage(role="user", content="токен " * 3000),
        ChatMessage(role="assistant", content="ответ " * 3000),
    ]
    repo = CompressionRepository(huge)
    gateway = ScriptedGateway([])
    with pytest.raises(ContextLimitExceeded):
        await build_agent(gateway, repo).run("chat-1", "ещё")


@pytest.mark.asyncio
async def test_summary_persisted_before_main_call_and_survives_error():
    repo = CompressionRepository(long_history())
    gateway = ScriptedGateway(
        [LLMResponse("свёртка", "fake-model", sample_usage()), LLMGatewayError("boom")]
    )
    with pytest.raises(LLMGatewayError):
        await build_agent(gateway, repo).run("chat-1", "вопрос")
    assert repo.summaries == [("chat-1", "свёртка", 14)]
```

Вспомогательные `sample_llm_response()`/`sample_usage()` — использовать существующие фейковые хелперы файла (`sample_usage()` уже есть; добавить `def sample_llm_response(): return LLMResponse("fake answer", "deepseek-chat", sample_usage())`), импорты `SYSTEM_PROMPT`, `LLMResponse`, `LLMGatewayError` дописать в импорты теста (часть есть). `long_history()` в тесте `test_compression_sums_up_then_sends_tail` должен давать >3000 токенов при `context_limit_tokens=20000` — если tiktoken посчитает меньше (русские ~3 токена/слово дают ~15k), подобрать число пар так, чтобы `history_tokens > 3000` и при этом хвост+свёртка < 20000; после запуска при FAIL подправить `filler` на `" " + "данные " * 25`.

- [ ] **Step 2: FAIL** — `.venv/bin/pytest tests/test_agent.py -q` (старые тесты проходят, новые — TypeError про `compress`/AttributeError `compression`).

- [ ] **Step 3: Реализация `Agent.run`** — переписать метод (валидация, `perf_counter` вокруг основного ответа, `build_dialog_usage` по полному хранилищу — как в day8):

```python
    async def run(
        self, chat_id: str, user_text: str, compress: bool = True
    ) -> AgentResult:
        message = self._validate_message(user_text)
        chat = await self._repository.get_chat(chat_id)
        new_message = ChatMessage(role="user", content=message)
        system_message = ChatMessage(role="system", content=SYSTEM_PROMPT)
        history = list(chat.messages)
        full_history_tokens = self._counter.count_messages(
            [system_message, *history]
        )
        request_tokens = self._counter.count_messages([new_message])

        compression: CompressionInfo | None = None
        if compress:
            old, recent = split_history(history, self._config.keep_recent_messages)
            if old and full_history_tokens > self._config.compress_at_tokens:
                summary, covers, summarization_usage = await self._ensure_summary(
                    chat, old
                )
                request_history = [build_summary_message(summary, covers), *recent]
                sent_history_tokens = self._counter.count_messages(
                    [system_message, *request_history]
                )
                saved = full_history_tokens - sent_history_tokens
                compression = CompressionInfo(
                    applied=True,
                    before_tokens=full_history_tokens,
                    after_tokens=sent_history_tokens,
                    saved_tokens=saved,
                    saved_percent=round(100 * saved / full_history_tokens),
                    summarization_tokens=summarization_usage.total_tokens,
                    summarization_cost_usd=summarization_cost_usd(
                        summarization_usage, self._config
                    ),
                )
                context = [system_message, *request_history, new_message]
            else:
                sent_history_tokens = full_history_tokens
                context = [system_message, *history, new_message]
        else:
            sent_history_tokens = full_history_tokens
            context = [system_message, *history, new_message]

        estimated = sent_history_tokens + request_tokens
        if estimated > self._config.context_limit_tokens:
            raise ContextLimitExceeded(
                estimated, self._config.context_limit_tokens
            )

        started_at = perf_counter()
        response = await self._gateway.complete(context)
        answer = response.text.strip()
        updated_chat = await self._repository.append_exchange(
            chat_id, message, answer, response.usage
        )

        dialog = build_dialog_usage(
            [system_message, *updated_chat.messages], self._counter, self._config
        )
        return AgentResult(
            answer=answer,
            model=response.model or self._model,
            duration_ms=round((perf_counter() - started_at) * 1000),
            stages=[...как в day8...],
            usage=UsageReport(
                request_tokens=request_tokens,
                history_tokens=sent_history_tokens,
                response_tokens=response.usage.completion_tokens,
                prompt_tokens_api=response.usage.prompt_tokens,
                completion_tokens_api=response.usage.completion_tokens,
                total_tokens_api=response.usage.total_tokens,
                dialog_total_tokens=dialog.dialog_total_tokens,
                dialog_cost_usd=dialog.dialog_cost_usd,
                context_limit=dialog.context_limit,
                context_remaining=dialog.context_remaining,
                warning=dialog.warning,
                compression=compression,
            ),
        )

    async def _ensure_summary(
        self, chat: Chat, old: list[ChatMessage]
    ) -> tuple[str, int, TokenUsage]:
        if chat.summary is not None and chat.summary_covers >= len(old):
            return chat.summary, chat.summary_covers, TokenUsage(0, 0, 0)
        response = await self._gateway.complete(
            build_summarization_messages(
                chat.summary, old, self._config.summary_max_tokens
            )
        )
        summary = response.text.strip()
        await self._repository.save_summary(chat.id, summary, len(old))
        return summary, len(old), response.usage
```
Импорты: `from app.application.compression import build_summarization_messages, build_summary_message, split_history`, `summarization_cost_usd` из usage, `Chat, ChatMessage, CompressionInfo, TokenUsage` из domain.
`UsageReport` в domain += поле `compression: CompressionInfo | None = None` (последним).
Существующие day8-тесты `test_agent.py` должны пройти без правок (compress=True по умолчанию, их истории короткие — ниже порога).

- [ ] **Step 4: PASS + регресс** — `.venv/bin/pytest -q` → Expected: `62 passed`.

- [ ] **Step 5: Commit** `git commit -am "feat: compress history with rolling summary in agent"`

---

### Task 5: HTTP-слой

**Files:**
- Modify: `day9/backend/app/presentation/schemas.py`
- Modify: `day9/backend/app/presentation/routes.py`
- Test: `day9/backend/tests/test_chat_api.py`

**Interfaces:**
- Consumes: `CompressionInfo`, `Agent.run(..., compress=...)`, `Chat.summary`.
- Produces: `POST /api/chats/{id}/messages` тело `{message, compress}`; `usage.compression` объект в ответе; `ChatDetailResponse.summary/summary_covers`.

- [ ] **Step 1: Падающие тесты** — дописать в `tests/test_chat_api.py` (по образцу существующих: `app.dependency_overrides`):

```python
def sample_compression():
    return CompressionInfo(
        applied=True,
        before_tokens=12000,
        after_tokens=1500,
        saved_tokens=10500,
        saved_percent=88,
        summarization_tokens=8000,
        summarization_cost_usd=0.0024,
    )


class RecordingAgent:
    def __init__(self):
        self.kwargs = None

    async def run(self, chat_id, user_text, compress=True):
        self.kwargs = {"chat_id": chat_id, "user_text": user_text, "compress": compress}
        base = sample_report()
        return AgentResult(
            answer="ok",
            model="fake",
            duration_ms=5,
            stages=[AgentStage(name="Agent", status="completed")],
            usage=UsageReport(**vars(base), compression=sample_compression()),
        )


def test_message_endpoint_passes_compress_and_returns_compression_report():
    agent = RecordingAgent()
    app.dependency_overrides[get_agent] = lambda: agent
    client = TestClient(app)
    response = client.post(
        "/api/chats/chat-1/messages",
        json={"message": "привет", "compress": False},
    )
    assert response.status_code == 200
    assert agent.kwargs["compress"] is False
    compression = response.json()["usage"]["compression"]
    assert compression["applied"] is True
    assert compression["saved_percent"] == 88
    app.dependency_overrides.clear()


def test_message_endpoint_compression_defaults_to_null():
    app.dependency_overrides[get_agent] = lambda: FakeAgent()  # day8-фейк без compression
    client = TestClient(app)
    response = client.post(
        "/api/chats/chat-1/messages", json={"message": "привет"}
    )
    assert response.status_code == 200
    assert response.json()["usage"]["compression"] is None
    app.dependency_overrides.clear()


def test_chat_detail_exposes_summary(client_with_fake_repo):
    response = client_with_fake_repo.get("/api/chats/chat-1")
    payload = response.json()
    assert payload["summary"] == "Свёртка диалога."
    assert payload["summary_covers"] == 6
```
`FakeRepository` из этого файла: добавить в конструктор `summary="Свёртка диалога.", summary_covers=6` в `Chat(...)` и метод `async def save_summary(self, *args, **kwargs): raise NotImplementedError` — нет, Protocol не проверяется рантайм-наследованием; просто добавить поля в `Chat`. Фикстуру `client_with_fake_repo` не выдумывать: использовать существующий в файле паттерн override `get_repository` (скопировать стиль соседних тестов). `RecordingAgent` в тесте default-вызова: существующий `FakeAgent` day8 имеет `async def run(self, chat_id, user_text)` — routes теперь шлёт `compress=` kwarg → **расширить `FakeAgent.run` подписью `(self, chat_id, user_text, compress=True)`** (минимальная правка существующего фейка; записать это отдельным шагом перед тестами).

- [ ] **Step 2: FAIL** — `.venv/bin/pytest tests/test_chat_api.py -q` → 422 на `compress`/KeyError `compression`/отсутствие summary-полей.

- [ ] **Step 3: Реализация**

`schemas.py`:
```python
class ChatMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    compress: bool = True
    # существующий валидатор остаётся


class CompressionResponse(BaseModel):
    applied: bool
    before_tokens: int
    after_tokens: int
    saved_tokens: int
    saved_percent: int
    summarization_tokens: int
    summarization_cost_usd: float
```
`UsageResponse` += `compression: CompressionResponse | None = None`.
`ChatDetailResponse` += `summary: str | None = None`, `summary_covers: int = 0`.

`routes.py` — send_message: `result = await agent.run(chat_id, request.message, compress=request.compress)`; вместо `UsageResponse(**vars(result.usage))`:
```python
def _usage_response(report: UsageReport) -> UsageResponse:
    data = dict(vars(report))
    compression = data.pop("compression")
    return UsageResponse(
        **data,
        compression=(
            CompressionResponse(**vars(compression)) if compression else None
        ),
    )
```
в `ChatDetailResponse(...)` добавить `summary=chat.summary, summary_covers=chat.summary_covers`. Импортировать `UsageReport` в routes для хелпера.

`dependencies.py` — `get_usage_config` += `compress_at_tokens=settings.compress_at_tokens, keep_recent_messages=settings.keep_recent_messages, summary_max_tokens=settings.summary_max_tokens`; в `settings.py` += 3 поля (defaults 3000/10/500); `.env.example` += `COMPRESS_AT_TOKENS=3000`, `KEEP_RECENT_MESSAGES=10`, `SUMMARY_MAX_TOKENS=500`.

- [ ] **Step 4: PASS + регресс** — `.venv/bin/pytest -q` → Expected: `65 passed`.

- [ ] **Step 5: Commit** `git commit -am "feat: expose compression via HTTP API"`

---

### Task 6: UI — тумблер и чип сжатия

**Files:**
- Modify: `day9/frontend/src/api.js`
- Modify: `day9/frontend/src/App.jsx`
- Modify: `day9/frontend/src/components/ChatPanel.jsx`
- Modify: `day9/frontend/src/styles.css`

**Interfaces:**
- Consumes: `usage.compression` из ответа API.
- Produces: `sendMessage(chatId, message, compress)`; state `compress` (persist `localStorage['day9-compress']`).

- [ ] **Step 1: api.js** — заменить `sendMessage`:

```js
export function sendMessage(chatId, message, compress = true) {
  return request(`/api/chats/${chatId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ message, compress }),
  });
}
```

- [ ] **Step 2: App.jsx** — состояние и прокидывание:

```js
const [compress, setCompress] = useState(
  () => localStorage.getItem('day9-compress') !== 'false'
);
const handleToggleCompress = () => {
  setCompress(current => {
    localStorage.setItem('day9-compress', String(!current));
    return !current;
  });
};
```
В `sendToChat`: `await sendMessage(selectedChatId, text, compress)`; в объект assistant-сообщения (туда, где уже ложится `usage`) добавить `compression: response.usage?.compression ?? null`. В JSX `<ChatPanel ... compress={compress} onToggleCompress={handleToggleCompress} />`.

- [ ] **Step 3: ChatPanel.jsx** — тумблер в composer и чип:

в form после textarea:
```jsx
        <label className="compress-toggle" title="Сворачивать старые сообщения в summary перед отправкой">
          <input
            type="checkbox"
            checked={compress}
            onChange={onToggleCompress}
            disabled={blocked}
          />
          Сжатие истории
        </label>
```
под markdown-пузырьком ассистента (рядом с `UsageLine`):
```jsx
            {item.role === 'assistant' && item.compression?.applied && (
              <div className="compression-chip">
                сжатие: {item.compression.before_tokens} → {item.compression.after_tokens} токенов
                (−{item.compression.saved_percent}%) · свёртка −${item.compression.summarization_cost_usd}
              </div>
            )}
```
(props `compress, onToggleCompress` добавить в сигнатуру компонента.)

- [ ] **Step 4: styles.css**

```css
.compress-toggle { display: flex; align-items: center; gap: 7px; font-size: 12px; color: #91a0a5; margin: 6px 2px 0; }
.compress-toggle input { accent-color: #4dd6bd; width: 15px; height: 15px; }
.compression-chip { display: inline-flex; margin-top: 6px; padding: 3px 10px; border-radius: 999px; border: 1px solid #39766a; background: rgba(77, 214, 189, 0.08); color: #79e3d0; font-size: 11px; letter-spacing: .02em; }
```

- [ ] **Step 5: Build + живой transform**

Run: `cd day9/frontend && npm run build` → `✓ built`; dev-сервер (из task 7) `curl -s http://localhost:5173/src/components/ChatPanel.jsx | grep -c compress-toggle` → `1`.

- [ ] **Step 6: Commit** `git commit -am "feat: compression toggle and savings chip in UI"`

---

### Task 7: Живое E2E, README, push-готовность

**Files:**
- Create: `day9/README.md`
- Modify: `README.md` (корневой — строка day9)
- Test: живой прогон скриптом

- [ ] **Step 1: Серверы**

```bash
lsof -ti tcp:8000 | xargs kill; lsof -ti tcp:5173 | xargs kill
cd day9/backend && nohup .venv/bin/uvicorn app.main:app --port 8000 > /tmp/day9-backend.log 2>&1 &
cd ../frontend && python3 -c "
import subprocess, os
os.chdir('/Users/nauruz/AIADVENTCHALLENGE/day9/frontend')
log = open('/tmp/day9-frontend.log','ab'); dn = open('/dev/null','rb')
print(subprocess.Popen(['node_modules/.bin/vite'], stdin=dn, stdout=log, stderr=log, start_new_session=True).pid)"
sleep 4 && curl -s http://127.0.0.1:8000/api/chats >/dev/null && echo backend-ok && curl -s -o /dev/null -w "frontend %{http_code}\n" http://localhost:5173/
```

- [ ] **Step 2: E2E сравнение до/после (живой DeepSeek!)** — скрипт:

```python
# scripts/day9_check.py — запуск: cd day9/backend && .venv/bin/python scripts/day9_check.py
import asyncio, json, urllib.request
from app.presentation.dependencies import get_repository

FILLER = " Расскажи про архитектуру агентных систем с примерами баз данных и очередями сообщений, детали не упускай." * 30

async def main():
    repo = get_repository()
    chat = await repo.create_chat()
    for turn in range(4):
        await repo.append_exchange(chat.id, f"вопрос {turn}{FILLER}", f"ответ {turn}{FILLER}", None)
    print(json.dumps({"chat_id": chat.id}))

asyncio.run(main())
```
(Скрипт только надувает историю без API-трат; затем два живых запроса curl — единственные платные ~$0.01.)
```bash
CHAT=$(создать через curl -sX POST localhost:8000/api/chats); надуть историю python-скриптом
# 1) без сжатия — полная история (считает все ~5-8k токенов):
curl -sX POST localhost:8000/api/chats/$CHAT/messages -H 'content-type: application/json' \
  -d '{"message":"Какое самое первое было сообщение? Ответь одной строкой.","compress":false}' \
  | python3 -c "import json,sys; u=json.load(sys.stdin)['usage']; print('compress=off prompt_api:',u['prompt_tokens_api'])"
# 2) со сжатием на том же чате:
curl -s ... -d '{"message":"А теперь?","compress":true}' \
  | python3 -c "import json,sys; r=json.load(sys.stdin); c=r['usage']['compression']; print('compress=on prompt_api:',r['usage']['prompt_tokens_api'],'| before/after:',c['before_tokens'],c['after_tokens'],'| saved:',c['saved_percent'],'%')"
```
Expected: `prompt_tokens_api` во втором случае ниже в разы; `compression.applied=true`, `saved_percent > 60`; ответ на «первое сообщение» опирается на summary.
- [ ] **Step 3: README day9** — постановка, механика (таблица env-параметров, схема запроса), ритуал сравнения качества (4 шага из spec), фактические цифры шага 2, «что ломается: сжатие не бесплатно, свёртка теряет детали, кумулятивный дрейф». Корневой README: строка day9 в список дней.
- [ ] **Step 4: Финальная регрессия** — `cd day9/backend && .venv/bin/pytest -q` → `65 passed`; `npm run build` ✓; `git status --short` чистый после коммита.
- [ ] **Step 5: Commit** `git commit -am "docs: day9 compression writeup with measured numbers"`

---

## Self-review

1. **Spec coverage:** тумблер UI (T6), rolling-summary+кэш (T4 `_ensure_summary`), пороги по токенам (T3/4 config), 413-страховка (T4 test_giant_tail), чип экономии и стоимость свёртки (T3/4/6), summary в GET (T5), сравнение (T7 ритуал). Гэпов нет.
2. **Placeholders:** «...как в day8...» в stages — единственное намеренное цитирование существующего кода; остальное развёрнуто.
3. **Типы:** `CompressionInfo` единажды (T3), используется T4/T5; `save_summary(chat_id, summary, covers)` одинаково в T2/T4; `Chat` поля — T2. `UsageReport.compression` default=None — обратная совместимость T5 (day8-фейки).
