# День 10: Context Strategies Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Агент с 4 режимами управления контекстом (full / sliding window / sticky facts / branching), переключателем в UI и автоматическим сравнением стратегий на скриптованном ТЗ-сценарии.

**Architecture:** Каждый день — самостоятельный проект. `day10` скаффолдится из `day9` с удалением summary-слоя. Стратегии — чистые функции сборки запроса (`context_strategy.py`); ветки и facts — часть модели `Chat`/репозитория; сравнение — отдельный сервис, гоняющий сценарий параллельно в 4 чатах с детерминированным скорингом.

**Tech Stack:** Python 3.13, FastAPI, pydantic-settings, tiktoken (cl100k_base), DeepSeek API, pytest + pytest-asyncio, React 19 + Vite 6, plain CSS.

**Spec:** `docs/superpowers/specs/2026-09-14-day10-context-strategies-design.md`

## Global Constraints

- Все команды backend — из `day10/backend` (Settings читает `.env` только из cwd).
- `DEEPSEEK_API_KEY` только в gitignored `day10/backend/.env`; ключ не печатать, не коммитить.
- UI-тексты и ответы модели — по-русски; код, идентификаторы, коммиты — английский; коммиты conventional (`feat:`/`chore:`/`docs:`/`fix:`).
- Работа прямо в `main` (разрешено пользователем).
- Хранилище никогда не удаляет сообщения ради экономии: режимы меняют только сборку запроса.
- Vite dev-сервер умирать не должен: запуск `nohup node_modules/.bin/vite > /tmp/day10-frontend.log 2>&1 & < /dev/null`; backend `nohup .venv/bin/uvicorn app.main:app --port 8000 > /tmp/day10-backend.log 2>&1 & < /dev/null`; освобождать порты `lsof -ti tcp:8000 | xargs kill`.
- pytest: `.venv/bin/pytest -q` (ожидаемый счётчик растёт от задачи к задаче, итог ~85).
- Референс сигнатур: `day9/backend/app/application/agent.py`, `compression.py`, `json_chat_repository.py` (удаляемый слой) и `day9/backend/tests/test_agent.py` (ScriptedGateway, FakeCounter `tokens ≈ len//4`).

---

### Task 1: Скаффолд `day10` и удаление summary-слоя

**Files:**
- Create: `day10/` (копий `day9/` за исключением `.venv`, `data`, `node_modules`, `.env`)
- Modify: `day10/backend/pyproject.toml`, `day10/backend/app/main.py`, `day10/backend/app/domain/models.py`, `day10/backend/app/application/agent.py`, `day10/backend/app/application/usage.py`, `day10/backend/app/infrastructure/json_chat_repository.py`, `day10/backend/app/infrastructure/settings.py`, `day10/backend/app/presentation/schemas.py`, `day10/backend/app/presentation/routes.py`, `day10/backend/.env.example`, файлы `day10/backend/tests/`
- Delete: `day10/backend/app/application/compression.py`, `day10/backend/tests/test_compression.py`
- Modify: `day10/frontend/package.json`, `day10/frontend/index.html`, `day10/frontend/src/App.jsx`, `day10/frontend/src/components/ChatPanel.jsx`, `day10/frontend/src/api.js`

**Interfaces:**
- Consumes: ничего.
- Produces: чистый day8-подобный app (плоский `Chat.messages`, `Agent.run(chat_id, user_text)`, без compress) в `day10/`; venv с установленными зависимостями; `node_modules`; `.env` с ключом.

- [ ] **Step 1: Копирование и переименования**

```bash
cd /Users/nauruz/AIADVENTCHALLENGE
rsync -a --exclude .venv --exclude data --exclude node_modules --exclude .env day9/ day10/
mkdir -p day10/backend/data
cd day10/backend && grep -rln day9 app tests pyproject.toml .env.example | xargs sed -i '' 's/day9/day10/g; s/Day 9/Day 10/g; s/день 9/день 10/g'
cd ../frontend && grep -rln day9 src index.html package.json | xargs sed -i '' 's/day9/day10/g; s/Day 9/Day 10/g'
```

В `day10/frontend/src/components/ChatPanel.jsx` hero-подпись: `DAY 10 · CONTEXT STRATEGIES`. В `app/main.py` заголовок FastAPI: `title="Day 10 Context Strategies"`.

- [ ] **Step 2: Удалить summary-слой backend**

- Удалить `app/application/compression.py`, `tests/test_compression.py`.
- `domain/models.py`: удалить `CompressionInfo`, поле `UsageReport.compression`, поля `Chat.summary`, `Chat.summary_covers`; в `UsageConfig` заменить `compress_at_tokens/keep_recent_messages/summary_max_tokens` на `sliding_window_messages: int = 10`, `facts_max_items: int = 20`.
- `application/usage.py`: удалить `summarization_cost_usd`.
- `application/agent.py`: `run(self, chat_id: str, user_text: str) -> AgentResult` — убрать ветку compression и `_ensure_summary`, собрать `context = [system_message, *history, new_message]`, `sent_history_tokens = full_history_tokens`; импорты compression/CompressionInfo удалить; `UsageReport(..., compression=...)` убрать.
- `infrastructure/json_chat_repository.py`: удалить `save_summary` и summary-поля в `_chat_to_dict/_chat_from_dict`.
- `presentation/schemas.py`: удалить `CompressionResponse`, `compress` в `ChatMessageRequest`, `compression` в `UsageResponse`, `summary/summary_covers` в `ChatDetailResponse`; `_usage_response` упростить до `UsageResponse(**vars(usage))`.
- `presentation/routes.py`: вернуть прямой вызов `agent.run(chat_id, request.message)` без `compress`.
- `infrastructure/settings.py`: `sliding_window_messages: int = 10`, `facts_max_items: int = 20` вместо трёх compress-полей.
- `.env.example`: `SLIDING_WINDOW_MESSAGES=10`, `FACTS_MAX_ITEMS=20` вместо `COMPRESS_AT_TOKENS/KEEP_RECENT_MESSAGES/SUMMARY_MAX_TOKENS`.
- `tests/`: удалить compression-тесты в `test_agent.py` (файл/классы, ссылающиеся на `compress`), `test_chat_api.py` (проверки `usage.compression`, поля `compress`), `test_usage.py` (тест `summarization_cost_usd`), `test_json_chat_repository.py` (summary round-trip, `save_summary`, legacy-summary-тест).

- [ ] **Step 3: Установить зависимости и перенести `.env`**

```bash
cd /Users/nauruz/AIADVENTCHALLENGE/day10/backend
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt
python3 - << 'EOF'
line = [l for l in open('../../day9/backend/.env') if l.startswith('DEEPSEEK_API_KEY')][0]
env = open('../../day9/backend/.env').read().replace('COMPRESS_AT_TOKENS', '# COMPRESS_AT_TOKENS')
open('.env', 'w').write(env)
EOF
git -C .. check-ignore -q day10/backend/.env && echo env-ignored  # проверка, что .env не попадёт в коммит
cd ../frontend && npm install --silent 2>&1 | tail -1
```

Ожидаемое содержимое `.env`: `DEEPSEEK_API_KEY=...`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_MODEL`, `CONTEXT_LIMIT_TOKENS=8000` (compress-строки удалить или закомментировать — Settings `extra="ignore"`).

- [ ] **Step 4: Прогнать тесты и сборку**

Run: `cd day10/backend && .venv/bin/pytest -q` → Expected: `48 passed` (±2, все зелёные).
Run: `cd day10/frontend && npm run build` → Expected: `✓ built`.

- [ ] **Step 5: Commit**

```bash
git add day10 && git commit -m "chore: scaffold day10 from day9 without compression layer"
```

---

### Task 2: Модель `Branch` и репозиторий веток/facts

**Files:**
- Modify: `day10/backend/app/domain/models.py`
- Modify: `day10/backend/app/infrastructure/json_chat_repository.py`
- Modify: `day10/backend/app/application/ports/chat_repository.py`
- Modify: `day10/backend/tests/test_json_chat_repository.py`
- Test: `day10/backend/tests/test_branches_repository.py` (создать, если решено вынести; иначе добавить в существующий)

**Interfaces:**
- Consumes: Task 1 (чистые `Chat`, `ChatMessage`, репозиторий).
- Produces:
  - `Branch(id: str, name: str, fork_at: int | None, messages: list[ChatMessage], facts: dict[str, str])` (mutable dataclass);
  - `Chat(..., branches: list[Branch], active_branch_id: str)` + properties `active_branch`, `messages`, `facts`;
  - `ChatRepository`: `append_exchange(chat_id, user_content, assistant_content, usage, branch_id=None)`, `save_facts(chat_id, branch_id, facts)`, `fork_branch(chat_id, after_index, name)`, `set_active_branch(chat_id, branch_id)`, `delete_branch(chat_id, branch_id)`; все async, возвращают `Chat`;
  - ошибки `BranchNotFound(RuntimeError)`, `LastBranchError(ValueError)`; невалидный `after_index` → `IndexError` (routes отловят в 400).

- [ ] **Step 1: Непроходящие тесты**

Добавить в `tests/test_json_chat_repository.py` (фикстуры `repository`/`chat` как в существующих тестах; `_raw_store` — helper, читающий json с `repository._path`; если нет — написать):

```python
import json

async def test_legacy_flat_chat_migrates_to_main_branch(repository, tmp_path):
    tmp_path.joinpath("chats.json").write_text(json.dumps({"chats": [{
        "id": "old", "title": "T", "created_at": "x", "updated_at": "y",
        "messages": [{"role": "user", "content": "привет"}],
    }]}, ensure_ascii=False), encoding="utf-8")
    chat = await repository.get_chat("old")
    assert [b.name for b in chat.branches] == ["main"]
    assert chat.active_branch_id == chat.branches[0].id
    assert chat.messages[0].content == "привет"
    assert chat.facts == {}

async def test_append_exchange_targets_active_branch(repository):
    chat = await repository.create_chat()
    updated = await repository.append_exchange(
        chat.id, "u", "a", TokenUsage(1, 1, 2)
    )
    assert updated.active_branch.messages[-1].content == "a"

async def test_fork_branch_copies_prefix_and_inherits_facts(repository):
    chat = await repository.create_chat()
    for i in range(4):
        chat = await repository.append_exchange(
            chat.id, f"u{i}", f"a{i}", TokenUsage(1, 1, 2)
        )
    chat = await repository.save_facts(chat.id, chat.active_branch_id, {"цель": "ТЗ"})
    forked = await repository.fork_branch(chat.id, 3, "ветка Б")
    assert len(forked.branches) == 2
    branch_b = forked.active_branch
    assert branch_b.name == "ветка Б"
    assert branch_b.fork_at == 3
    assert [m.content for m in branch_b.messages if m.role == "user"] == ["u0", "u1"]
    assert branch_b.facts == {"цель": "ТЗ"}

async def test_fork_branch_index_out_of_range(repository):
    chat = await repository.create_chat()
    chat = await repository.append_exchange(chat.id, "u", "a", TokenUsage(1, 1, 2))
    with pytest.raises(IndexError):
        await repository.fork_branch(chat.id, 99, "x")

async def test_switch_and_delete_branch(repository):
    chat = await repository.create_chat()
    chat = await repository.append_exchange(chat.id, "u", "a", TokenUsage(1, 1, 2))
    chat = await repository.fork_branch(chat.id, 1, "Б")
    main = next(b for b in chat.branches if b.name == "main")
    chat = await repository.set_active_branch(chat.id, main.id)
    assert chat.active_branch_id == main.id
    chat = await repository.delete_branch(chat.id, next(b.id for b in chat.branches if b.id != main.id))
    assert len(chat.branches) == 1
    with pytest.raises(LastBranchError):
        await repository.delete_branch(chat.id, chat.branches[0].id)
    with pytest.raises(BranchNotFound):
        await repository.set_active_branch(chat.id, "нет-такой")

async def test_facts_survive_restart(tmp_path, repository):
    chat = await repository.create_chat()
    await repository.save_facts(chat.id, chat.active_branch_id, {"a": "1"})
    fresh = JsonChatRepository(tmp_path / "chats.json")
    reloaded = await fresh.get_chat(chat.id)
    assert reloaded.facts == {"a": "1"}
```

- [ ] **Step 2: FAIL**

Run: `cd day10/backend && .venv/bin/pytest tests/test_json_chat_repository.py -q` → Expected: errors (`Branch`/методы не существуют).

- [ ] **Step 3: Реализовать models.py**

```python
from dataclasses import dataclass, field

@dataclass
class Branch:
    id: str
    name: str
    fork_at: int | None = None
    messages: list[ChatMessage] = field(default_factory=list)
    facts: dict[str, str] = field(default_factory=dict)

@dataclass
class Chat:
    id: str
    title: str
    created_at: str
    updated_at: str
    branches: list[Branch]
    active_branch_id: str

    @property
    def active_branch(self) -> Branch:
        for branch in self.branches:
            if branch.id == self.active_branch_id:
                return branch
        raise BranchNotFound(self.active_branch_id)

    @property
    def messages(self) -> list[ChatMessage]:
        return self.active_branch.messages

    @property
    def facts(self) -> dict[str, str]:
        return self.active_branch.facts

class BranchNotFound(RuntimeError):
    pass

class LastBranchError(ValueError):
    pass
```

Старый `Chat.messages` как поле удалить; `ChatSummary` без изменений.

- [ ] **Step 4: Реализовать репозиторий**

В `json_chat_repository.py`:

```python
def _branch_to_dict(branch: Branch) -> dict:
    return {
        "id": branch.id, "name": branch.name, "fork_at": branch.fork_at,
        "facts": branch.facts,
        "messages": [_message_to_dict(m) for m in branch.messages],
    }

def _branch_from_dict(data: dict) -> Branch:
    return Branch(
        id=data["id"], name=data["name"], fork_at=data.get("fork_at"),
        messages=[_message_from_dict(m) for m in data["messages"]],
        facts=dict(data.get("facts", {})),
    )

def _chat_to_dict(chat: Chat) -> dict:
    return {
        "id": chat.id, "title": chat.title,
        "created_at": chat.created_at, "updated_at": chat.updated_at,
        "active_branch_id": chat.active_branch_id,
        "branches": [_branch_to_dict(b) for b in chat.branches],
    }

def _chat_from_dict(data: dict) -> Chat:
    if "branches" in data:
        branches = [_branch_from_dict(b) for b in data["branches"]]
        active = data["active_branch_id"]
    else:  # legacy плоский формат дня 6-9
        branch = Branch(id=str(uuid4()), name="main", messages=[
            _message_from_dict(m) for m in data.get("messages", [])
        ])
        branches, active = [branch], branch.id
    return Chat(
        id=data["id"], title=data["title"],
        created_at=data["created_at"], updated_at=data["updated_at"],
        branches=branches, active_branch_id=active,
    )
```

`create_chat` — одна ветка `Branch(uuid4(), "main")`, `active_branch_id=branch.id`. Общие хелперы `_find_chat(store, chat_id)` / `_find_branch(chat, branch_id)` (бросает `BranchNotFound`, `branch_id=None` → active). `append_exchange(..., branch_id=None)`: `for`-цикл store заменить на чтение через `get_chat`+мутирование ветки, либо точечно по найденному dict — ключевое: append в `branch["messages"]`, `updated_at`, заголовок по первому сообщению активной ветки. `save_facts`, `fork_branch`:

```python
async def fork_branch(self, chat_id, after_index, name):
    async with self._lock:
        store = self._read_store()
        chat = _chat_from_dict(_find_chat(store, chat_id))
        source = chat.active_branch
        if not 0 <= after_index <= len(source.messages):
            raise IndexError(after_index)
        new = Branch(
            id=str(uuid4()), name=name, fork_at=after_index,
            messages=[replace(m) for m in source.messages[:after_index]],
            facts=dict(source.facts),
        )
        chat.branches.append(new)
        chat.active_branch_id = new.id
        chat.updated_at = _now()
        store["chats"] = [_chat_to_dict(c) if c["id"] != chat_id else _chat_to_dict(chat) for c in store["chats"]]
        self._write_store(store)
        return chat
```

(Допустим эквивалентный аккуратный вариант с dict-мутацией, главное — атомарность под `self._lock` и те же семантики.) `set_active_branch`, `delete_branch` (последняя → `LastBranchError`; после удаления активной — активна первая; new active branch fallback) — аналогично. Обновить protocol в `ports/chat_repository.py`.

- [ ] **Step 5: GREEN + коммит**

Run: `cd day10/backend && .venv/bin/pytest -q` → Expected: все passed (агент пока использует `chat.messages` — property спасает; если `create_chat` в `agent`/routes сломался — починить использование). Ожидаемо ~54 passed.

```bash
git add day10/backend && git commit -m "feat: add branches and facts storage with legacy migration"
```

---

### Task 3: Чистые стратегии сборки контекста

**Files:**
- Create: `day10/backend/app/application/context_strategy.py`
- Test: `day10/backend/tests/test_context_strategy.py`

**Interfaces:**
- Consumes: `Branch`, `ChatMessage`, `UsageConfig(sliding_window_messages, facts_max_items)`.
- Produces:
  - `CONTEXT_MODES = ("full", "sliding", "facts", "branching")`
  - `assemble_history(mode: str, branch: Branch, new_message: ChatMessage, config: UsageConfig) -> list[ChatMessage]` — history-часть (facts-блок первым для `facts`, окно — срез; без system-промпта);
  - `build_facts_message(facts: dict[str, str]) -> ChatMessage | None` (None для `{}`);
  - `build_facts_update_messages(facts: dict[str, str], user_text: str, limit: int) -> list[ChatMessage]`;
  - `parse_facts_update(raw_text: str, limit: int) -> dict[str, str] | None` — None если JSON не найден/не словарь; значения → str; cap `limit`.
  - Для `full`/`branching` — вся `branch.messages`.

- [ ] **Step 1: Тесты**

```python
import pytest
from app.application.context_strategy import (
    CONTEXT_MODES, assemble_history, build_facts_message,
    build_facts_update_messages, parse_facts_update,
)
from app.domain.models import Branch, ChatMessage, UsageConfig

def msg(role, content): return ChatMessage(role=role, content=content)

@pytest.fixture
def branch():
    messages = [msg("user", f"u{i}") if i % 2 == 0 else msg("assistant", f"a{i}")
                for i in range(12)]
    return Branch(id="b", name="main", messages=messages, facts={"цель": "ТЗ"})

@pytest.fixture
def config(): return UsageConfig(context_limit_tokens=8000,
                                 sliding_window_messages=10, facts_max_items=20)

def test_context_modes_exact():
    assert CONTEXT_MODES == ("full", "sliding", "facts", "branching")

def test_full_sends_entire_history(branch, config):
    out = assemble_history("full", branch, msg("user", "new"), config)
    assert out == branch.messages + [msg("user", "new")]

def test_branching_like_full(branch, config):
    out = assemble_history("branching", branch, msg("user", "new"), config)
    assert out == branch.messages + [msg("user", "new")]

def test_sliding_keeps_window_plus_new(branch, config):
    out = assemble_history("sliding", branch, msg("user", "new"), config)
    assert out == branch.messages[-10:] + [msg("user", "new")]

def test_facts_block_plus_window(branch, config):
    out = assemble_history("facts", branch, msg("user", "new"), config)
    assert out[0].role == "system" and "цель: ТЗ" in out[0].content
    assert out[1:] == branch.messages[-10:] + [msg("user", "new")]

def test_unknown_mode_rejected(branch, config):
    with pytest.raises(ValueError):
        assemble_history("summary", branch, msg("user", "new"), config)

def test_build_facts_message_empty_none():
    assert build_facts_message({}) is None

def test_facts_update_prompt_includes_current_and_new():
    messages = build_facts_update_messages({"цель": "ТЗ"}, "бюджет 1200", 20)
    assert messages[0].role == "system" and "facts" in messages[0].content.lower()
    assert "цель" in messages[0].content or "цель" in messages[1].content
    assert "бюджет 1200" in messages[1].content

def test_parse_facts_update_plain_json_and_cap():
    raw = json.dumps({f"k{i}": str(i) for i in range(30)}, ensure_ascii=False)
    parsed = parse_facts_update(raw, limit=20)
    assert len(parsed) == 20 and parsed["k0"] == "0"

def test_parse_facts_update_fenced_and_prose():
    assert parse_facts_update('Вот обновлённый JSON:\n```json\n{"a": 1}\n```', 20) == {"a": "1"}

def test_parse_facts_update_garbage_returns_none():
    assert parse_facts_update("фактов не нашлось", 20) is None
```

(+ `import json` в начало.)

- [ ] **Step 2: FAIL** — `pytest tests/test_context_strategy.py -q` (ModuleNotFoundError).

- [ ] **Step 3: Реализация**

```python
import json
import re

from app.domain.models import Branch, ChatMessage, UsageConfig

CONTEXT_MODES = ("full", "sliding", "facts", "branching")

FACTS_UPDATER_SYSTEM_PROMPT = (
    "You maintain a compact key-value facts memory of a dialogue in Russian. "
    "Given current facts (JSON) and the newest user message, return the FULL "
    "updated facts JSON: goals, constraints, preferences, decisions, "
    "agreements, numbers, names. Keep keys short Russian labels. Merge, do "
    "not duplicate. Output only JSON object, no prose."
)

def build_facts_message(facts):
    if not facts:
        return None
    lines = "\n".join(f"- {key}: {value}" for key, value in sorted(facts.items()))
    return ChatMessage(role="system", content=f"Известные факты о задаче:\n{lines}")

def assemble_history(mode, branch, new_message, config):
    if mode not in CONTEXT_MODES:
        raise ValueError(f"Unknown context mode: {mode}")
    if mode in ("full", "branching"):
        return [*branch.messages, new_message]
    window = config.sliding_window_messages
    if mode == "sliding":
        return [*branch.messages[-window:], new_message]
    facts_message = build_facts_message(branch.facts)
    history = branch.messages[-window:]
    if facts_message is None:
        return [*history, new_message]
    return [facts_message, *history, new_message]

def build_facts_update_messages(facts, user_text, limit):
    user_prompt = (
        f"Текущие факты:\n{json.dumps(facts, ensure_ascii=False)}\n\n"
        f"Новое сообщение пользователя:\n{user_text}\n\n"
        f"Верни обновлённые факты JSON (не больше {limit} записей)."
    )
    return [
        ChatMessage(role="system", content=FACTS_UPDATER_SYSTEM_PROMPT),
        ChatMessage(role="user", content=user_prompt),
    ]

def parse_facts_update(raw_text, limit):
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    cleaned = {str(k): str(v) for k, v in data.items()}
    return dict(list(cleaned.items())[:limit])
```

- [ ] **Step 4: GREEN** — `pytest tests/test_context_strategy.py -q` (11 passed).
- [ ] **Step 5: Commit** — `git add day10/backend && git commit -m "feat: add pure context strategy assembly"`

---

### Task 4: Режимы в Agent + `ContextInfo`

**Files:**
- Modify: `day10/backend/app/domain/models.py`
- Modify: `day10/backend/app/application/agent.py`
- Modify: `day10/backend/app/application/usage.py` (helper `fact_update_cost_usd` → переиспользовать `exchange_cost_usd`, раунд)
- Test: `day10/backend/tests/test_agent.py` (добавить класс режимов)

**Interfaces:**
- Consumes: Task 2 (`Chat.active_branch`, `save_facts`), Task 3 (`assemble_history`, `build_facts_update_messages`, `parse_facts_update`).
- Produces: `Agent.run(chat_id: str, user_text: str, mode: str = "sliding") -> AgentResult`; `ContextInfo(mode, sent_messages, total_messages, facts_count, fact_update_tokens, fact_update_cost_usd)`; `UsageReport.context: ContextInfo | None = None`.

- [ ] **Step 1: Тесты** (в `tests/test_agent.py`; фикстуры `ScriptedGateway`/`FakeCounter`/repo-мок reuse; `UsageConfig(context_limit_tokens=8000, sliding_window_messages=4, facts_max_items=20)`):

```python
def make_chat_with_branch(history_messages, facts=None):
    branch = Branch(id="b1", name="main", messages=history_messages, facts=facts or {})
    return Chat(id="c1", title="T", created_at="x", updated_at="y",
                branches=[branch], active_branch_id="b1")

class RecordingRepository:  # если в файле уже есть mock-репо с replace-like семантикой — расширить его
    def __init__(self, chat): self.chat = chat; self.saved_facts = []
    async def get_chat(self, chat_id): return self.chat
    async def save_facts(self, chat_id, branch_id, facts):
        self.saved_facts.append((branch_id, dict(facts)))
        self.chat.active_branch.facts = dict(facts)
        return self.chat
    async def append_exchange(self, chat_id, user_content, assistant_content, usage, branch_id=None):
        self.chat.active_branch.messages.extend([
            ChatMessage(role="user", content=user_content),
            ChatMessage(role="assistant", content=assistant_content, usage=usage),
        ])
        return self.chat

async def test_full_mode_sends_everything(agent_factory):
    chat = make_chat_with_branch([msg("user", f"u{i}") for i in range(10)])
    gateway = ScriptedGateway([LLMResponse(text="ok", model="m", usage=TokenUsage(9, 3, 12))])
    result = await agent_factory(gateway, RecordingRepository(chat)).run("c1", "新作", mode="full")
    assert len(gateway.calls[0]) == 10 + 2  # system + 10 + new
    assert result.usage.context.mode == "full"
    assert result.usage.context.fact_update_tokens == 0

async def test_sliding_mode_window_only(agent_factory):
    chat = make_chat_with_branch([msg("user", f"u{i}") for i in range(10)])
    gateway = ScriptedGateway([LLMResponse(text="ok", model="m", usage=TokenUsage(9, 3, 12))])
    result = await agent_factory(gateway, RecordingRepository(chat)).run("c1", "новое", mode="sliding")
    sent = gateway.calls[0]
    assert len(sent) == 1 + 4 + 1  # system + окно(4) + новое
    assert result.usage.context.sent_messages == 4
    assert result.usage.context.total_messages == 10

async def test_facts_mode_extracts_then_prepends_and_saves(agent_factory):
    chat = make_chat_with_branch([msg("user", "бюджет 1200")], facts={})
    gateway = ScriptedGateway([
        LLMResponse(text='{"бюджет": "1200"}', model="m", usage=TokenUsage(40, 10, 50)),  # экстрактор
        LLMResponse(text="ok", model="m", usage=TokenUsage(30, 5, 35)),                     # основной
    ])
    repo = RecordingRepository(chat)
    result = await agent_factory(gateway, repo).run("c1", "бюджет 1200", mode="facts")
    assert repo.saved_facts == [("b1", {"бюджет": "1200"})]
    assert gateway.calls[1][1].role == "system" and "бюджет: 1200" in gateway.calls[1][1].content
    assert result.usage.context.fact_update_tokens == 50
    assert result.usage.context.fact_update_cost_usd > 0

async def test_facts_mode_garbage_extraction_keeps_old(agent_factory):
    chat = make_chat_with_branch([msg("user", "у")], facts={"старый": "факт"})
    gateway = ScriptedGateway([
        LLMResponse(text="не json вовсе", model="m", usage=TokenUsage(40, 10, 50)),
        LLMResponse(text="ok", model="m", usage=TokenUsage(30, 5, 35)),
    ])
    repo = RecordingRepository(chat)
    await agent_factory(gateway, repo).run("c1", "у", mode="facts")
    assert repo.saved_facts == [] and repo.chat.facts == {"старый": "факт"}

async def test_precheck_uses_assembled_not_full_history(agent_factory):
    chat = make_chat_with_branch([msg("user", "x" * 400) for _ in range(20)])  # 20*~100 токенов
    config = UsageConfig(context_limit_tokens=600, sliding_window_messages=4, facts_max_items=20)
    agent = agent_factory(ScriptedGateway([]), RecordingRepository(chat), config=config)
    result = await agent.run("c1", "y", mode="sliding")   # полный контекст >600, окно — нет
    assert result.usage.context.mode == "sliding"
    with pytest.raises(ContextLimitExceeded):
        await agent.run("c1", "y", mode="full")
```

`ScriptedGateway.calls` — список отправленных message-list (если текущий мок не сохраняет calls — добавить `self.calls.append(messages)` в `complete`).

- [ ] **Step 2: FAIL** (нет `mode`/`ContextInfo`).
- [ ] **Step 3: Реализация.** `ContextInfo` в models; `UsageReport.context`. В `agent.run`:

```python
async def run(self, chat_id: str, user_text: str, mode: str = "sliding") -> AgentResult:
    message = self._validate_message(user_text)
    chat = await self._repository.get_chat(chat_id)
    branch = chat.active_branch
    new_message = ChatMessage(role="user", content=message)
    system_message = ChatMessage(role="system", content=SYSTEM_PROMPT)

    fact_update_tokens, fact_update_cost = 0, 0.0
    facts_count = len(branch.facts)
    if mode == "facts":
        extraction = await self._gateway.complete(
            build_facts_update_messages(
                branch.facts, message, self._config.facts_max_items
            )
        )
        updated = parse_facts_update(extraction.text, self._config.facts_max_items)
        if updated is not None:
            await self._repository.save_facts(chat_id, branch.id, updated)
            facts_count = len(updated)
        fact_update_tokens = extraction.usage.total_tokens
        fact_update_cost = round(exchange_cost_usd(extraction.usage, self._config), 6)

    request_history = assemble_history(mode, branch, new_message, self._config)
    sent_messages = len(branch.messages) if mode in ("full", "branching") else min(
        self._config.sliding_window_messages, len(branch.messages)
    )
    context = [system_message, *request_history]
    sent_history_tokens = self._counter.count_messages(context)
    request_tokens = self._counter.count_messages([new_message])
    if sent_history_tokens + request_tokens > self._config.context_limit_tokens:
        raise ContextLimitExceeded(
            sent_history_tokens + request_tokens, self._config.context_limit_tokens
        )
    # ...gateway.complete(context), append_exchange(chat_id, message, answer, usage, branch_id=branch.id)
    # ...UsageReport(context=ContextInfo(mode=mode, sent_messages=sent_messages,
    #        total_messages=len(branch.messages), facts_count=facts_count,
    #        fact_update_tokens=fact_update_tokens, fact_update_cost_usd=fact_update_cost), ...)
```

(Хвост — как в day9 без compression; `build_dialog_usage` оставить по полной ветке.)

- [ ] **Step 4: GREEN** — `pytest -q` (все, ~65).
- [ ] **Step 5: Commit** — `git commit -m "feat: run agent under four context modes with fact extraction"`

---

### Task 5: HTTP-слой: mode, ветки, facts, текст 413

**Files:**
- Modify: `day10/backend/app/presentation/schemas.py`, `routes.py`, `app/infrastructure/settings.py` (проверить Task 1 поля), `app/main.py`
- Test: `day10/backend/tests/test_chat_api.py` (+ новые тесты endpoints)

**Interfaces:**
- Consumes: Task 4 `Agent.run(..., mode)`, Task 2 repo-методы.
- Produces:
  - `POST /api/chats/{id}/messages` body `{"message": str, "mode": "full"|"sliding"|"facts"|"branching"}` → `usage.context {mode, sent_messages, total_messages, facts_count, fact_update_tokens, fact_update_cost_usd}`;
  - `GET /api/chats/{id}` → `branches: [{id,name,fork_at,facts,messages}]`, `active_branch_id`;
  - `POST /api/chats/{id}/branches` `{"after_message_index": int, "name": str}` → 200 detail; 400 неверный индекс; 404 нет чата;
  - `PATCH /api/chats/{id}/active-branch` `{"branch_id": str}`; `DELETE /api/chats/{id}/branches/{branch_id}` → 409 `LastBranchError`;
  - `PATCH /api/chats/{id}/facts` `{"facts": {str: str}}` (в активную ветку, cap `FACTS_MAX_ITEMS`).
  - 413 detail: «…Сообщение не отправлено и не сохранено. Смените режим на «Окно» или «Факты» или начните новый чат.»

- [ ] **Step 1: Тесты** (httpx AsyncClient фикстуры reuse; в `test_chat_api.py`):

```python
async def test_message_request_accepts_mode_and_returns_context(client, created_chat):
    chat_id = created_chat
    r = await client.post(f"/api/chats/{chat_id}/messages",
                          json={"message": "привет", "mode": "sliding"})
    assert r.status_code == 200
    assert r.json()["usage"]["context"]["mode"] == "sliding"

async def test_invalid_mode_rejected(client, created_chat):
    r = await client.post(f"/api/chats/{created_chat}/messages",
                          json={"message": "х", "mode": "summary"})
    assert r.status_code == 422

async def test_branch_lifecycle_over_http(client, chat_with_history):
    chat_id, _ = chat_with_history
    r = await client.post(f"/api/chats/{chat_id}/branches",
                          json={"after_message_index": 2, "name": "Б"})
    assert r.status_code == 200
    detail = r.json()
    assert len(detail["branches"]) == 2 and detail["active_branch_id"] == detail["branches"][-1]["id"]
    b_id = detail["branches"][0]["id"]
    assert (await client.patch(f"/api/chats/{chat_id}/active-branch",
            json={"branch_id": b_id})).status_code == 200
    assert (await client.delete(f"/api/chats/{chat_id}/branches/{b_id}")).status_code == 200
    assert (await client.delete(f"/api/chats/{chat_id}/branches/{b_id}")).status_code == 404

async def test_facts_patch_caps_and_persists(client, created_chat):
    facts = {f"k{i}": "v" for i in range(30)}
    r = await client.patch(f"/api/chats/{created_chat}/facts", json={"facts": facts})
    assert r.status_code == 200 and len(r.json()["facts"]) == 20
```

`chat_with_history` — фикстура: создать чат, 1 обмен (2 сообщения) через POST messages (gateway — фикстура-заглушка app), вернуть (chat_id, ids).

- [ ] **Step 2: FAIL**, **Step 3: Реализация** (pydantic `Literal` для mode; handlers тонкие — вызывают repository напрямую; `_chat_detail_payload(chat)` общий хелпер; исключение→status: `IndexError→400`, `ChatNotFound/BranchNotFound→404`, `LastBranchError→409` через `except` в handler; cap facts в handler: `dict(list(items)[:settings.facts_max_items])`), **Step 4: GREEN** (~72), **Step 5: Commit** `git commit -m "feat: expose modes, branches and facts over HTTP"`.

---

### Task 6: Compare-сервис (скрипт, скоринг, раннер)

**Files:**
- Create: `day10/backend/app/application/compare.py`
- Modify: `day10/backend/app/presentation/routes.py`, `schemas.py`
- Test: `day10/backend/tests/test_compare.py`

**Interfaces:**
- Consumes: `Agent.run`, `ChatRepository.create_chat/append_exchange`.
- Produces:
  - `SCENARIO_TURNS: list[str]` (10 сообщений «собираем ТЗ»), `CONTROL_FACTS: dict[str, str]` (метка → подстрока-очаждаемое: `{"кодовое имя": "Буревестник", "бюджет": "1200", "срок": "15 декабря", "инфраструктура": "без внешнего облака", "хранилище": "PostgreSQL", "ритуал": "отчёт по пятницам"}`), `FINAL_QUESTION: str`;
  - `check_survival(answer: str) -> dict[str, bool]`;
  - `CompareModeResult(mode, chat_id, survived: dict, prompt_tokens, completion_tokens, calls, duration_ms, error: str|None)`;
  - `ContextComparator(agent, repository).run(modes=CONTEXT_MODES) -> list[CompareModeResult]` — `asyncio.gather` по режимам; в режиме `branching` форк после 5-го обмена через repo (`fork_branch(name="ветка Б")`), продолжение в ветке; cost не хранит (UI считает из токенов по ценам settings);
  - `POST /api/compare` → `list[CompareResponse]`.

- [ ] **Step 1: Тесты**

```python
import pytest
from app.application.compare import (
    CONTROL_FACTS, SCENARIO_TURNS, check_survival, ContextComparator,
)
from app.domain.models import LLMResponse, TokenUsage

def test_scenario_has_all_control_facts():
    joined = "\n".join(SCENARIO_TURNS) + FINAL_QUESTION
    for label, needle in CONTROL_FACTS.items():
        assert needle in joined, label

def test_check_survival_detects_missing():
    answer = "ТЗ: код Буревестник, бюджет 1200"
    survived = check_survival(answer)
    assert survived["кодовое имя"] and survived["бюджет"]
    assert not survived["срок"]

async def test_comparator_runs_all_modes_and_scores(compare_agent_factory):
    # gateway-заглушка: для финального вопроса отвечает все 6 подстрок, иначе "ок"
    agent, repo, gateway = compare_agent_factory(final_answer_full_memory=True)
    results = await ContextComparator(agent, repo).run(("full", "sliding", "facts", "branching"))
    assert [r.mode for r in results] == ["full", "sliding", "facts", "branching"]
    assert len(await repo.list_chats()) == 4  # по одному чату на режим, двойных create нет
    assert all(sum(r.survived.values()) == 6 for r in results)
    assert all(r.error is None and r.calls >= 11 for r in results)
    sliding = next(r for r in results if r.mode == "sliding")
    assert sliding.prompt_tokens < next(r for r in results if r.mode == "full").prompt_tokens

async def test_comparator_isolates_mode_failure(compare_agent_factory):
    agent, repo, gateway = compare_agent_factory(fail_mode="facts")
    results = await ContextComparator(agent, repo).run(("facts", "full"))
    assert next(r for r in results if r.mode == "facts").error is not None
    assert next(r for r in results if r.mode == "full").error is None
```

`compare_agent_factory` — фикстура в этом же файле: FakeCounter (len//4), ScriptedGateway с ответом на лету (замыкает `CONTROL_FACTS.values()` в финальный ответ), in-memory repo (подойдёт `JsonChatRepository(tmp_path/…)`). Реализация фикстуры — по образцу `tests/test_agent.py`.

- [ ] **Step 2: FAIL**, **Step 3: Реализация** (`compare.py`:

```python
class ContextComparator:
    def __init__(self, agent, repository):
        ...
    async def run(self, modes=CONTEXT_MODES):
        return list(await asyncio.gather(*(self._run_mode(m) for m in modes)))

    async def _run_mode(self, mode):
        chat = await self._repository.create_chat()
        try:
            for turn_index, turn in enumerate(SCENARIO_TURNS, start=1):
                chat = await self._agent.run(chat.id, turn, mode=mode)  # AgentResult->chat: берите chat из repo.get_chat после обмена
                if mode == "branching" and turn_index == 5:
                    detail = await self._repository.get_chat(chat.id)
                    await self._repository.fork_branch(
                        chat.id, len(detail.messages), "ветка Б"
                    )
            final = await self._agent.run(chat.id, FINAL_QUESTION, mode=mode)
            return CompareModeResult(..., survived=check_survival(final.answer),
                prompt_tokens=..., calls=...)
        except Exception as exc:
            return CompareModeResult(..., error=str(exc)[:300], survived=check_survival(""))
```

`Agent.run` возвращает `AgentResult` (без chat_id) — идентификатор чата Comparator держит сам; токены/вызовы аккумулировать из `result.usage` каждого обмена (facts-режим: +экстракторные вызовы и токенты учитываются в `calls`/`prompt_tokens`). Тест фиксирует: ровно 4 созданных чата (по одному на режим), `calls >= 11`.
Точная реализация — по тестам; тесты — контракт целиком.
), **Step 4: GREEN** (~76), **Step 5: Commit** `git commit -m "feat: add strategy comparison runner with scripted scenario"`

---

### Task 7: UI — переключатель режимов, табы веток, панель фактов

**Files:**
- Modify: `day10/frontend/src/App.jsx`, `api.js`, `components/ChatPanel.jsx`
- Create: `day10/frontend/src/components/FactsPanel.jsx`, `day10/frontend/src/components/ModeSelector.jsx`
- Modify: `day10/frontend/src/styles.css`

**Interfaces:**
- Consumes: API Task 5.
- Produces: функции `api.js`: `sendMessage(chatId, message, mode)`, `createBranch(chatId, index, name)`, `setActiveBranch(chatId, branchId)`, `deleteBranch(chatId, branchId)`, `updateFacts(chatId, facts)`; состояние App: `mode` (persist `localStorage['day10-mode']`, дефолт `"sliding"`), `branches`/`activeBranchId` из GET detail.

- [ ] **Step 1: `ModeSelector.jsx`**

```jsx
const MODES = [
  ['full', 'Полный'], ['sliding', 'Окно'], ['facts', 'Факты'], ['branching', 'Ветки'],
];
export default function ModeSelector({ mode, onChange, disabled }) {
  return (
    <div className="mode-selector" role="radiogroup" aria-label="Режим контекста">
      {MODES.map(([value, label]) => (
        <button key={value} type="button" role="radio" aria-checked={mode === value}
          className={mode === value ? 'mode active' : 'mode'}
          disabled={disabled} onClick={() => onChange(value)}>
          {label}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: `FactsPanel.jsx`** — список `branch.facts` (key→value), кнопка ✏ открывает input/textarea на строку, 🗑 удаляет, строка «+ добавить» с двумя инпутами; пропсы `{facts, onAdd, onUpdate, onDelete}`, все изменения одним `onChange(nextFacts)` родит отправляет в `updateFacts`. Скрыт, если `mode !== 'facts'`.

- [ ] **Step 3: App.jsx** — состояние `mode` + `useEffect(localStorage.setItem)`; `sendMessage(chatId, text, mode)`; `handleFactsChange(next)` → `updateFacts`, обновить detail; табы: рендер `chat.branches.map(b => <button className={b.id===active?'tab active':'tab'} onClick={setActiveBranch(...)}>)`, при смене — перезагрузка detail; кнопка «🌿 Ветвиться отсюда» у каждой assistant-реплики (показывать только `mode==='branching'`): `createBranch(chatId, index, 'ветка ' + (branches.length+1))` → обновить detail. Чип под ответом из `usage.context`: `окно: 10 из 23` / `факты: 7 + 10 сообщений, экстракция −$0.000…` / `полный: 23`.

- [ ] **Step 4: CSS** — `.mode-selector` (сегменты), `.branch-tabs .tab(.active)`, `.facts-panel` (список, строки, кнопки), `.context-chip`.

- [ ] **Step 5: Проверка** — `npm run build` → `✓`; вручную не надо (Task 9). Commit `git commit -m "feat: mode selector, branch tabs and facts panel"`

---

### Task 8: UI — кнопка и таблица сравнения

**Files:**
- Create: `day10/frontend/src/components/ComparePanel.jsx`
- Modify: `day10/frontend/src/App.jsx`, `api.js`, `styles.css`

**Interfaces:**
- Consumes: `POST /api/compare` (Task 6), таблица формата `CompareModeResult`.
- Produces: `runCompare()` в `api.js`; панель Compare: кнопка «⚖ Сравнить стратегии», состояние `comparing` (spinner, long-poll ~1–3 мин), `compareRows`; клик по строке → `openChat(chat_id)` (переход в обычный режим с этим чатом).

- [ ] **Step 1: `ComparePanel.jsx`**

```jsx
function FactChips({ survived }) {
  return Object.entries(survived).map(([label, ok]) => (
    <span key={label} className={ok ? 'chip ok' : 'chip bad'}>{ok ? '✔' : '✘'} {label}</span>
  ));
}
export default function ComparePanel({ rows, comparing, onStart, onOpenChat, error }) {
  return (
    <section className="compare">
      <button type="button" onClick={onStart} disabled={comparing}>
        {comparing ? 'Прогоняю сценарий ТЗ во всех режимах…' : '⚖ Сравнить стратегии'}
      </button>
      {error && <p className="compare-error">{error}</p>}
      {rows && (
        <table className="compare-table">
          <thead><tr><th>Режим</th><th>Факты уцелели</th><th>Токены</th><th>Вызовы</th><th>Сек</th><th></th></tr></thead>
          <tbody>{rows.map(r => (
            <tr key={r.mode} className={r.error ? 'row-error' : ''}>
              <td>{MODE_LABELS[r.mode]}</td>
              <td>{r.error ? r.error : <>{FactChips({ survived: r.survived })}<span> {sum(r.survived)}/6</span></>}</td>
              <td>{r.prompt_tokens + r.completion_tokens}</td>
              <td>{r.calls}</td>
              <td>{(r.duration_ms / 1000).toFixed(1)}</td>
              <td><button type="button" onClick={() => onOpenChat(r.chat_id)}>открыть</button></td>
            </tr>))}
          </tbody>
        </table>
      )}
    </section>
  );
}
```

(`MODE_LABELS` вынести из ModeSelector в общий модуль/проп.)

- [ ] **Step 2: интеграция** — App: `compareRows/compareError` state, `onStart` → `runCompare()` (api.js: fetch POST `/api/compare`, timeout не ставим), после — `refreshChats()` (чаты `⚖ …` появятся). Рендерить под `ModeSelector`.
- [ ] **Step 3: CSS** — `.compare-table` (полоски строк, `.ok/.bad` чипы зелёный/красный), spinner — disabled-кнопка + текст.
- [ ] **Step 4: `npm run build`** → ✓. Commit `git commit -m "feat: strategy comparison table in UI"`

---

### Task 9: Живое E2E, README, финальная регрессия

**Files:**
- Create: `day10/README.md`
- Modify: `README.md` (корневой)

- [ ] **Step 1: Запустить** backend (8000) + frontend (5173) командами из Global Constraints.
- [ ] **Step 2: Ручная проверка UI-ритуала** (curl-аналог допустим): создать чат, 12 сообщений по ~200 токенов в `sliding` → чип `окно: 10 из N`; включить `facts` → в GET `facts` непустой, панель показывает ключи; `branching` → fork после 6, вторая ветка с другим вопросом, переключение табов меняет ленту. Все три — обязательны.
- [ ] **Step 3: Живое сравнение**: `curl -s --max-time 600 -X POST localhost:8000/api/compare | tee /tmp/day10-compare.json` → таблица из 4 строк; ожидаемо: `full`/`branching` 6/6, `facts` 5-6/6, `sliding` < 6 (окно вытеснило контрольные ходы); токены `full` ≫ `sliding`. Если sliding набрал 6/6 — усилить сценарий (ранние сообщения длиннее) и повторить; реальный результат зафиксировать в README.
- [ ] **Step 4: README** (`day10/README.md`): постановка дня; таблица режимов и env (`SLIDING_WINDOW_MESSAGES`, `FACTS_MAX_ITEMS`); как читать чипы; сценарий ТЗ и контрольные факты (полный список); вклеить фактическую таблицу сравнения из `/tmp/day10-compare.json` (режимы, выживание по фактам, токены, вызовы, сек) и разбор «почему sliding теряет ранние факты, facts дороже по вызовам, ветвление не экономит токены»; ритуал ручного сравнения; «честные ограничения» (substring-скоринг грубый, один сценарий ≠ статистика, compare-результаты не персистентны, ветки без merge); запуск/API/тесты/структура — как в day9.
- [ ] **Step 5: Корневой `README.md`** — строка `- [\`day10\`](./day10) — стратегии контекста: sliding window, sticky facts и ветвление с автосравнением на одном сценарии.`
- [ ] **Step 6: Регрессия** `cd day10/backend && .venv/bin/pytest -q` → все passed (~80+); `cd day10/frontend && npm run build` → ✓.
- [ ] **Step 7: Commit** `git add day10 README.md && git commit -m "docs: day10 strategies writeup with measured comparison"`

---

## Self-review (заполняется после написания)

- Покрытие спеки: §0 Task 1, §1 Task 2, §2 Task 3–4, §3 Task 4–5, §4 Task 2+5+7, §5 Task 6+8, §6 Task 1+7, ошибки Task 5, тесты по всем Task'ам. ✓
- Заглушки: в Task 6 пометка «реализация скелетная, воспроизвести по тестам» — осознанно допускаем, тесты задают контракт целиком; двойной `create_chat` в скелете помечен NOTE и запрещён тестом `[r.mode for r in results]` без дублей чатов (уточнить в тесте: 4 чата, а не 8 — добавить assert `len(repo_chats) == 4`).
- Типы: `ContextInfo` поля согласованы Task 4 ↔ Task 5 ↔ Task 7; `CompareModeResult` Task 6 ↔ Task 8 (`duration_ms`, `calls`, `survived`).
