# День 11. Модель памяти ассистента — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Построить ассистента с тремя раздельно хранимыми слоями памяти (краткосрочная, рабочая, долговременная) и явной политикой записи: модель предлагает кандидатов → пользователь подтверждает, плюс команда `запомни:`.

**Architecture:** Форк `day10` (FastAPI + React + DeepSeek). Ветки/стратегии/compare удаляются. Домен: `Chat` (messages + `WorkingMemory`), глобальные `LongTermMemory` и `MemoryCandidate`. Три хранилища: `data/chats/<id>.json`, `data/long_term.json`, `data/candidates.json`. `memory.py` собирает промпт из трёх подписанных блоков. `agent.run` пишет историю, ищет кандидатов, собирает промпт, вызывает модель.

**Tech Stack:** Python 3.11+, FastAPI, pydantic v2, pytest + pytest-asyncio, tiktoken, openai SDK (DeepSeek), React 18 + Vite.

## Global Constraints

- Python `>=3.11`; новые зависимости **не добавляются** (используем только `requirements.txt` дня 10).
- `day6`–`day10` **не изменяются**; вся работа в `day11/`.
- Пользовательские тексты UI и ошибок — на русском.
- TDD: сначала падающий тест, потом реализация, потом коммит на задачу.
- Предел контекста: `CONTEXT_LIMIT_TOKENS=8000` (поведение дня 8 сохраняется).
- Порты по умолчанию: backend `8000`, frontend `5173` (README просит остановить day10).
- Категории долговременной памяти строго: `profile`, `decisions`, `knowledge`.
- Статус рабочей памяти: `active` | `done`.

---

### Task 1: Скаффолдинг day11 из day10

**Files:**
- Create: `day11/` (копия `day10/`)
- Delete: `day11/backend/app/application/context_strategy.py`
- Delete: `day11/backend/app/application/compare.py`
- Delete: `day11/backend/app/infrastructure/json_chat_repository.py`
- Delete: `day11/backend/app/presentation/routes.py`
- Delete: `day11/backend/app/presentation/schemas.py`
- Delete: `day11/backend/app/presentation/dependencies.py`
- Delete: `day11/backend/app/application/agent.py`
- Delete: `day11/backend/tests/test_context_strategy.py`
- Delete: `day11/backend/tests/test_compare.py`
- Delete: `day11/backend/tests/test_agent.py`
- Delete: `day11/backend/tests/test_chat_api.py`
- Delete: `day11/backend/tests/test_json_chat_repository.py`
- Delete: `day11/frontend/src/components/ModeSelector.jsx`
- Delete: `day11/frontend/src/components/FactsPanel.jsx`
- Delete: `day11/frontend/src/components/ComparePanel.jsx`
- Delete: `day11/backend/data/` (если есть), `day11/backend/advent_challenge_day9_backend.egg-info/`

**Interfaces:**
- Consumes: ничего.
- Produces: каталог `day11/` со скелетом; сохранены `app/domain/models.py`, `app/application/usage.py`, `app/application/ports/*`, `app/infrastructure/deepseek_gateway.py`, `app/infrastructure/token_counter.py`, `app/infrastructure/settings.py`, `app/main.py`, frontend `ChatSidebar.jsx`, `MarkdownMessage.jsx`, `AgentFlow.jsx`, `UsagePanel.jsx`.

- [ ] **Step 1: Скопировать day10 в day11**

Run (PowerShell):
```powershell
Copy-Item -Recurse -Force day10 day11
```
Expected: появился `day11/` с backend и frontend.

- [ ] **Step 2: Удалить устаревшие backend-файлы**

Run (PowerShell):
```powershell
Remove-Item day11/backend/app/application/context_strategy.py
Remove-Item day11/backend/app/application/compare.py
Remove-Item day11/backend/app/infrastructure/json_chat_repository.py
Remove-Item day11/backend/app/presentation/routes.py
Remove-Item day11/backend/app/presentation/schemas.py
Remove-Item day11/backend/app/presentation/dependencies.py
Remove-Item day11/backend/app/application/agent.py
Remove-Item day11/backend/tests/test_context_strategy.py
Remove-Item day11/backend/tests/test_compare.py
Remove-Item day11/backend/tests/test_agent.py
Remove-Item day11/backend/tests/test_chat_api.py
Remove-Item day11/backend/tests/test_json_chat_repository.py
Remove-Item -Recurse -Force day11/backend/advent_challenge_day9_backend.egg-info -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force day11/backend/data -ErrorAction SilentlyContinue
```

- [ ] **Step 3: Удалить устаревшие frontend-компоненты**

Run (PowerShell):
```powershell
Remove-Item day11/frontend/src/components/ModeSelector.jsx
Remove-Item day11/frontend/src/components/FactsPanel.jsx
Remove-Item day11/frontend/src/components/ComparePanel.jsx
```

- [ ] **Step 4: Проверить, что day10 не тронут и day11 на месте**

Run:
```powershell
git status --short
Test-Path day11/backend/app/domain/models.py
Test-Path day11/backend/app/infrastructure/deepseek_gateway.py
```
Expected: в `git status` только новые `day11/...`; оба `Test-Path` → `True`; файлы `day10/` не в списке изменений.

- [ ] **Step 5: Обновить имена пакета**

Modify `day11/backend/pyproject.toml`:
```toml
[project]
name = "advent-challenge-day11-backend"
```
Modify `day11/backend/app/main.py` (строка заголовка приложения будет заменена целиком в Task 6; сейчас достаточно поменять title):
```python
app = FastAPI(title="Day 11 Assistant Memory Model")
```

- [ ] **Step 6: Commit**

```bash
git add day11
git commit -m "chore: scaffold day11 from day10 skeleton"
```

---

### Task 2: Доменные модели

**Files:**
- Modify: `day11/backend/app/domain/models.py`
- Test: `day11/backend/tests/test_models.py`

**Interfaces:**
- Consumes: ничего.
- Produces:
  - `TokenUsage(prompt_tokens, completion_tokens, total_tokens)`
  - `UsageConfig(context_limit_tokens=8000, input_price_per_million=0.30, output_price_per_million=1.20, long_term_max_per_category=50, long_term_max_item_chars=500)`
  - `WorkingMemory(goal="", constraints=[], decisions=[], status="active")` c `is_empty`
  - `LongTermEntry(id, text, source_chat_id, created_at)`
  - `LongTermMemory(profile=[], decisions=[], knowledge=[])` c `entries(category)`, `total_count()`
  - `MemoryCandidate(id, text, category, source_chat_id, status="pending", created_at="")`
  - `ChatMessage(role, content, usage=None)`, `LLMResponse(text, model, usage)`, `AgentStage(name, status)`, `AgentResult(answer, model, duration_ms, stages, usage)`
  - `ChatSummary(id, title, created_at, updated_at)`
  - `Chat(id, title, created_at, updated_at, messages=[], working_memory=WorkingMemory())`
  - `MemoryInfo(long_term_count, long_term_tokens, working_tokens, history_tokens, candidate_tokens)`
  - `DialogUsage(...)`, `UsageReport(..., memory: MemoryInfo | None = None)`
  - Исключения: `InvalidUserMessage`, `ChatNotFound`, `ChatPersistenceError`, `LLMGatewayError`, `AuthenticationGatewayError`, `RateLimitGatewayError`, `GatewayTimeoutError`, `CandidateNotFound`, `CandidateConflict`, `LongTermEntryNotFound`, `ContextLimitExceeded`
  - Константа `LONG_TERM_CATEGORIES = ("profile", "decisions", "knowledge")`

- [ ] **Step 1: Написать падающий тест**

Create `day11/backend/tests/test_models.py`:
```python
from app.domain.models import (
    LONG_TERM_CATEGORIES,
    Chat,
    LongTermEntry,
    LongTermMemory,
    UsageConfig,
    WorkingMemory,
)


def test_categories_match_spec():
    assert LONG_TERM_CATEGORIES == ("profile", "decisions", "knowledge")


def test_working_memory_empty_and_filled():
    assert WorkingMemory().is_empty is True
    assert WorkingMemory(goal="Собрать ТЗ").is_empty is False
    assert WorkingMemory(constraints=["бюджет 900"]).is_empty is False


def test_long_term_memory_entries_and_count():
    entry = LongTermEntry(
        id="e1", text="аллергия на арахис", source_chat_id="c1", created_at="t"
    )
    long_term = LongTermMemory(knowledge=[entry])

    assert long_term.entries("knowledge") == [entry]
    assert long_term.entries("profile") == []
    assert long_term.total_count() == 1


def test_chat_defaults_to_empty_memory():
    chat = Chat(id="c1", title="T", created_at="a", updated_at="b")

    assert chat.messages == []
    assert chat.working_memory.is_empty is True
    assert chat.working_memory.status == "active"


def test_usage_config_memory_defaults():
    config = UsageConfig()

    assert config.long_term_max_per_category == 50
    assert config.long_term_max_item_chars == 500
```

- [ ] **Step 2: Запустить тест — должен упасть**

Run: `cd day11/backend && python -m pytest tests/test_models.py -q`
Expected: FAIL (`ImportError: cannot import name 'LONG_TERM_CATEGORIES'`).

- [ ] **Step 3: Переписать models.py**

Replace `day11/backend/app/domain/models.py` полностью:
```python
from dataclasses import dataclass, field
from typing import Literal


StageStatus = Literal["pending", "active", "completed", "error"]
WorkingStatus = Literal["active", "done"]
CandidateStatus = Literal["pending", "approved", "rejected"]

LONG_TERM_CATEGORIES = ("profile", "decisions", "knowledge")


@dataclass(frozen=True)
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(frozen=True)
class UsageConfig:
    context_limit_tokens: int = 8000
    input_price_per_million: float = 0.30
    output_price_per_million: float = 1.20
    long_term_max_per_category: int = 50
    long_term_max_item_chars: int = 500


@dataclass(frozen=True)
class MemoryInfo:
    long_term_count: int
    long_term_tokens: int
    working_tokens: int
    history_tokens: int
    candidate_tokens: int


@dataclass(frozen=True)
class DialogUsage:
    history_tokens: int
    dialog_total_tokens: int
    dialog_cost_usd: float
    context_limit: int
    context_remaining: int
    warning: bool


@dataclass(frozen=True)
class UsageReport:
    request_tokens: int
    history_tokens: int
    response_tokens: int
    prompt_tokens_api: int
    completion_tokens_api: int
    total_tokens_api: int
    dialog_total_tokens: int
    dialog_cost_usd: float
    context_limit: int
    context_remaining: int
    warning: bool
    memory: MemoryInfo | None = None


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["system", "user", "assistant"]
    content: str
    usage: TokenUsage | None = None


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    usage: TokenUsage


@dataclass(frozen=True)
class AgentStage:
    name: str
    status: StageStatus


@dataclass(frozen=True)
class AgentResult:
    answer: str
    model: str
    duration_ms: int
    stages: list[AgentStage]
    usage: UsageReport


@dataclass(frozen=True)
class ChatSummary:
    id: str
    title: str
    created_at: str
    updated_at: str


@dataclass
class WorkingMemory:
    goal: str = ""
    constraints: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    status: str = "active"

    @property
    def is_empty(self) -> bool:
        return not self.goal.strip() and not self.constraints and not self.decisions


@dataclass
class LongTermEntry:
    id: str
    text: str
    source_chat_id: str
    created_at: str


@dataclass
class LongTermMemory:
    profile: list[LongTermEntry] = field(default_factory=list)
    decisions: list[LongTermEntry] = field(default_factory=list)
    knowledge: list[LongTermEntry] = field(default_factory=list)

    def entries(self, category: str) -> list[LongTermEntry]:
        return getattr(self, category)

    def total_count(self) -> int:
        return len(self.profile) + len(self.decisions) + len(self.knowledge)


@dataclass
class MemoryCandidate:
    id: str
    text: str
    category: str
    source_chat_id: str
    status: str = "pending"
    created_at: str = ""


@dataclass
class Chat:
    id: str
    title: str
    created_at: str
    updated_at: str
    messages: list[ChatMessage] = field(default_factory=list)
    working_memory: WorkingMemory = field(default_factory=WorkingMemory)


class InvalidUserMessage(ValueError):
    pass


class ChatNotFound(RuntimeError):
    pass


class ChatPersistenceError(RuntimeError):
    pass


class CandidateNotFound(RuntimeError):
    pass


class CandidateConflict(ValueError):
    pass


class LongTermEntryNotFound(RuntimeError):
    pass


class LLMGatewayError(RuntimeError):
    pass


class AuthenticationGatewayError(LLMGatewayError):
    pass


class RateLimitGatewayError(LLMGatewayError):
    pass


class GatewayTimeoutError(LLMGatewayError):
    pass


class ContextLimitExceeded(RuntimeError):
    def __init__(self, estimated_tokens: int = 0, context_limit: int = 0):
        super().__init__(
            f"Context limit exceeded: {estimated_tokens}/{context_limit}"
        )
        self.estimated_tokens = estimated_tokens
        self.context_limit = context_limit
```

- [ ] **Step 4: Запустить тест — должен пройти**

Run: `cd day11/backend && python -m pytest tests/test_models.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Проверить, что usage.py не сломан**

`app/application/usage.py` не импортирует удалённые сущности, изменения не нужны.
Run: `cd day11/backend && python -m pytest tests/test_usage.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add day11/backend/app/domain/models.py day11/backend/tests/test_models.py
git commit -m "feat(day11): three-layer memory domain models"
```

---

### Task 3: Сборка промпта и парсеры памяти

**Files:**
- Create: `day11/backend/app/application/memory.py`
- Test: `day11/backend/tests/test_memory.py`

**Interfaces:**
- Consumes: `Chat`, `ChatMessage`, `LongTermMemory`, `LongTermEntry`, `WorkingMemory`, `LONG_TERM_CATEGORIES`.
- Produces:
  - `LONG_TERM_CATEGORIES`, `CATEGORY_LABELS: dict[str, str]`
  - `build_long_term_block(long_term) -> ChatMessage | None`
  - `build_working_block(working) -> ChatMessage | None`
  - `build_prompt(chat, long_term, system_prompt) -> list[ChatMessage]`
  - `parse_memory_command(text) -> str | None`
  - `build_candidate_messages(user_text, answer, long_term, limit) -> list[ChatMessage]`
  - `parse_candidates(raw_text, limit) -> list[dict]` (элементы `{"text": str, "category": str}`)
  - `parse_command_category(raw_text) -> str` (fallback `"knowledge"`)

- [ ] **Step 1: Написать падающий тест**

Create `day11/backend/tests/test_memory.py`:
```python
from app.application.memory import (
    build_candidate_messages,
    build_long_term_block,
    build_prompt,
    build_working_block,
    parse_candidates,
    parse_command_category,
    parse_memory_command,
)
from app.domain.models import (
    Chat,
    ChatMessage,
    LongTermEntry,
    LongTermMemory,
    WorkingMemory,
)


def entry(text, category="knowledge"):
    return LongTermEntry(
        id=text, text=text, source_chat_id="c1", created_at="t"
    )


def chat_with(messages, working=None):
    return Chat(
        id="c1",
        title="T",
        created_at="a",
        updated_at="b",
        messages=messages,
        working_memory=working or WorkingMemory(),
    )


def test_empty_long_term_and_working_are_not_injected():
    assert build_long_term_block(LongTermMemory()) is None
    assert build_working_block(WorkingMemory()) is None


def test_done_working_memory_is_not_injected():
    working = WorkingMemory(goal="Собрать ТЗ", status="done")

    assert build_working_block(working) is None


def test_long_term_block_lists_categories():
    long_term = LongTermMemory(
        profile=[entry("Науруз", "profile")],
        knowledge=[entry("аллергия на арахис")],
    )

    block = build_long_term_block(long_term)

    assert "## Долговременная память" in block.content
    assert "профиль:" in block.content
    assert "- Науруз" in block.content
    assert "- аллергия на арахис" in block.content


def test_working_block_renders_fields():
    working = WorkingMemory(
        goal="Собрать ТЗ",
        constraints=["бюджет 900"],
        decisions=["PostgreSQL"],
    )

    block = build_working_block(working)

    assert "Цель: Собрать ТЗ" in block.content
    assert "- бюджет 900" in block.content
    assert "- PostgreSQL" in block.content


def test_build_prompt_order_system_longterm_working_history():
    long_term = LongTermMemory(profile=[entry("Науруз", "profile")])
    chat = chat_with(
        [ChatMessage(role="user", content="привет")],
        working=WorkingMemory(goal="ТЗ"),
    )

    prompt = build_prompt(chat, long_term, "SYS")

    assert [m.role for m in prompt] == ["system", "system", "system", "user"]
    assert prompt[0].content == "SYS"
    assert "Долговременная" in prompt[1].content
    assert "Рабочая" in prompt[2].content
    assert prompt[3].content == "привет"


def test_parse_memory_command_variants():
    assert parse_memory_command("запомни: я аллергик") == "я аллергик"
    assert parse_memory_command("Запомни, что люблю Kotlin") == "люблю Kotlin"
    assert parse_memory_command("запомни что тест") == "тест"
    assert parse_memory_command("просто сообщение") is None


def test_parse_candidates_filters_and_caps():
    raw = (
        '[{"text": "аллергия на арахис", "category": "knowledge"},'
        ' {"text": "мусор", "category": "unknown"},'
        ' {"text": "используем PostgreSQL", "category": "decisions"}]'
    )

    result = parse_candidates(raw, 5)

    assert result == [
        {"text": "аллергия на арахис", "category": "knowledge"},
        {"text": "используем PostgreSQL", "category": "decisions"},
    ]


def test_parse_candidates_garbage_returns_empty():
    assert parse_candidates("не json", 5) == []


def test_parse_command_category_falls_back_to_knowledge():
    assert parse_command_category("не json") == "knowledge"
    assert (
        parse_command_category('[{"text": "x", "category": "profile"}]')
        == "profile"
    )


def test_build_candidate_messages_includes_existing():
    long_term = LongTermMemory(knowledge=[entry("аллергия")])

    messages = build_candidate_messages("привет", "ответ", long_term, 3)

    assert messages[0].role == "system"
    assert "аллергия" in messages[1].content
    assert "привет" in messages[1].content
```

- [ ] **Step 2: Запустить тест — должен упасть**

Run: `cd day11/backend && python -m pytest tests/test_memory.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.application.memory'`).

- [ ] **Step 3: Написать memory.py**

Create `day11/backend/app/application/memory.py`:
```python
import json
import re

from app.domain.models import (
    LONG_TERM_CATEGORIES,
    Chat,
    ChatMessage,
    LongTermMemory,
    WorkingMemory,
)

CATEGORY_LABELS = {
    "profile": "профиль",
    "decisions": "решения",
    "knowledge": "знания",
}
MEMORY_COMMAND_PREFIXES = ("запомни:", "запомни, что", "запомни что")
DEFAULT_CATEGORY = "knowledge"

CANDIDATE_SYSTEM_PROMPT = (
    "Ты извлекаешь кандидатов в долговременную память ассистента. "
    "Долговременная память хранит только устойчивые данные: профиль пользователя "
    "(profile: имя, роль, язык, привычки), принятые решения (decisions: «используем "
    "PostgreSQL»), устойчивые знания и предпочтения (knowledge: «аллергия на арахис»). "
    "Не предлагай разовые детали диалога, приветствия и текущую задачу. "
    'Верни JSON-массив объектов {"text": str, "category": '
    '"profile"|"decisions"|"knowledge"}. Если нечего запоминать — верни []. '
    "Только JSON, без пояснений."
)


def build_long_term_block(long_term: LongTermMemory) -> ChatMessage | None:
    if long_term.total_count() == 0:
        return None
    lines: list[str] = []
    for category in LONG_TERM_CATEGORIES:
        entries = long_term.entries(category)
        if not entries:
            continue
        lines.append(f"{CATEGORY_LABELS[category]}:")
        lines.extend(f"- {item.text}" for item in entries)
    return ChatMessage(
        role="system",
        content="## Долговременная память (глобальная)\n" + "\n".join(lines),
    )


def build_working_block(working: WorkingMemory) -> ChatMessage | None:
    if working.status == "done" or working.is_empty:
        return None
    lines: list[str] = []
    if working.goal.strip():
        lines.append(f"Цель: {working.goal.strip()}")
    if working.constraints:
        lines.append("Ограничения:")
        lines.extend(f"- {item}" for item in working.constraints)
    if working.decisions:
        lines.append("Решения:")
        lines.extend(f"- {item}" for item in working.decisions)
    return ChatMessage(
        role="system",
        content="## Рабочая память (текущая задача)\n" + "\n".join(lines),
    )


def build_prompt(
    chat: Chat, long_term: LongTermMemory, system_prompt: str
) -> list[ChatMessage]:
    messages = [ChatMessage(role="system", content=system_prompt)]
    long_term_block = build_long_term_block(long_term)
    if long_term_block is not None:
        messages.append(long_term_block)
    working_block = build_working_block(chat.working_memory)
    if working_block is not None:
        messages.append(working_block)
    messages.extend(chat.messages)
    return messages


def parse_memory_command(text: str) -> str | None:
    stripped = text.strip()
    lowered = stripped.lower()
    for prefix in MEMORY_COMMAND_PREFIXES:
        if lowered.startswith(prefix):
            return stripped[len(prefix):].strip()
    return None


def build_candidate_messages(
    user_text: str,
    answer: str,
    long_term: LongTermMemory,
    limit: int,
) -> list[ChatMessage]:
    existing: list[str] = []
    for category in LONG_TERM_CATEGORIES:
        existing.extend(item.text for item in long_term.entries(category))
    user_prompt = (
        "Уже сохранено в долговременной памяти:\n"
        + (json.dumps(existing, ensure_ascii=False) if existing else "[]")
        + f"\n\nНовое сообщение пользователя:\n{user_text}\n\n"
        + f"Ответ ассистента:\n{answer}\n\n"
        + f"Верни не больше {limit} новых кандидатов."
    )
    return [
        ChatMessage(role="system", content=CANDIDATE_SYSTEM_PROMPT),
        ChatMessage(role="user", content=user_prompt),
    ]


def parse_candidates(raw_text: str, limit: int) -> list[dict]:
    match = re.search(r"\[.*\]", raw_text, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    result: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        category = str(item.get("category", "")).strip()
        if not text or category not in LONG_TERM_CATEGORIES:
            continue
        result.append({"text": text, "category": category})
        if len(result) >= limit:
            break
    return result


def parse_command_category(raw_text: str) -> str:
    candidates = parse_candidates(raw_text, 1)
    if candidates:
        return candidates[0]["category"]
    return DEFAULT_CATEGORY
```

- [ ] **Step 4: Запустить тест — должен пройти**

Run: `cd day11/backend && python -m pytest tests/test_memory.py -q`
Expected: PASS (11 passed).

- [ ] **Step 5: Commit**

```bash
git add day11/backend/app/application/memory.py day11/backend/tests/test_memory.py
git commit -m "feat(day11): three-layer prompt assembly and memory parsers"
```

---

### Task 4: Репозиторий раздельного хранения

**Files:**
- Create: `day11/backend/app/infrastructure/json_memory_repository.py`
- Test: `day11/backend/tests/test_memory_repository.py`

**Interfaces:**
- Consumes: доменные модели из Task 2.
- Produces: `JsonMemoryRepository(chats_dir: Path, long_term_path: Path, candidates_path: Path)` со методами:
  - `create_chat(title="Новый чат") -> Chat`
  - `list_chats() -> list[ChatSummary]`
  - `get_chat(chat_id) -> Chat` (нет файла → `ChatNotFound`)
  - `delete_chat(chat_id) -> None` (нет файла → `ChatNotFound`)
  - `append_exchange(chat_id, user_content, assistant_content, usage) -> Chat`
  - `clear_messages(chat_id) -> Chat`
  - `get_working_memory(chat_id) -> WorkingMemory`
  - `save_working_memory(chat_id, working: WorkingMemory) -> Chat`
  - `complete_working_memory(chat_id) -> Chat`
  - `reset_working_memory(chat_id) -> Chat`
  - `get_long_term() -> LongTermMemory`
  - `replace_long_term(long_term: LongTermMemory) -> LongTermMemory`
  - `add_long_term_entry(category, text, source_chat_id) -> LongTermEntry` (дубль text в категории → `CandidateConflict`)
  - `delete_long_term_entry(category, entry_id) -> None` (нет → `LongTermEntryNotFound`)
  - `add_candidates(items: list[dict], source_chat_id) -> list[MemoryCandidate]` (дедуп pending по text)
  - `list_candidates(status="pending") -> list[MemoryCandidate]`
  - `approve_candidate(candidate_id) -> LongTermEntry` (нет → `CandidateNotFound`; не pending → `CandidateConflict`; дубль text → `CandidateConflict`)
  - `reject_candidate(candidate_id) -> MemoryCandidate`
  - `clear_rejected_candidates() -> int`

- [ ] **Step 1: Написать падающий тест**

Create `day11/backend/tests/test_memory_repository.py`:
```python
import json

import pytest

from app.domain.models import (
    CandidateConflict,
    CandidateNotFound,
    ChatNotFound,
    ChatPersistenceError,
    LongTermEntryNotFound,
    LongTermMemory,
    TokenUsage,
    WorkingMemory,
)
from app.infrastructure.json_memory_repository import JsonMemoryRepository


def repo(tmp_path):
    return JsonMemoryRepository(
        chats_dir=tmp_path / "chats",
        long_term_path=tmp_path / "long_term.json",
        candidates_path=tmp_path / "candidates.json",
    )


@pytest.mark.asyncio
async def test_three_memory_types_live_in_separate_files(tmp_path):
    repository = repo(tmp_path)
    chat = await repository.create_chat()
    await repository.append_exchange(chat.id, "привет", "ответ", TokenUsage(1, 1, 2))
    await repository.add_long_term_entry("knowledge", "аллергия", chat.id)
    await repository.add_candidates(
        [{"text": "люблю Kotlin", "category": "profile"}], chat.id
    )

    assert (tmp_path / "chats" / f"{chat.id}.json").exists()
    assert (tmp_path / "long_term.json").exists()
    assert (tmp_path / "candidates.json").exists()
    chat_payload = json.loads((tmp_path / "chats" / f"{chat.id}.json").read_text())
    assert "working_memory" in chat_payload
    assert "knowledge" not in chat_payload


@pytest.mark.asyncio
async def test_chat_crud_and_clear_history(tmp_path):
    repository = repo(tmp_path)
    chat = await repository.create_chat()
    await repository.append_exchange(chat.id, "u", "a", TokenUsage(1, 1, 2))

    cleared = await repository.clear_messages(chat.id)

    assert cleared.messages == []
    assert (await repository.get_chat(chat.id)).messages == []
    assert [c.id for c in await repository.list_chats()] == [chat.id]
    await repository.delete_chat(chat.id)
    with pytest.raises(ChatNotFound):
        await repository.get_chat(chat.id)


@pytest.mark.asyncio
async def test_working_memory_persists_overwrite_and_lifecycle(tmp_path):
    repository = repo(tmp_path)
    chat = await repository.create_chat()

    await repository.save_working_memory(
        chat.id, WorkingMemory(goal="бюджет 500", constraints=["500"])
    )
    await repository.save_working_memory(
        chat.id, WorkingMemory(goal="бюджет 900", constraints=["900"])
    )
    reloaded = await repo(tmp_path).get_working_memory(chat.id)
    assert reloaded.goal == "бюджет 900"
    assert reloaded.constraints == ["900"]

    done = await repository.complete_working_memory(chat.id)
    assert done.working_memory.status == "done"

    reset = await repository.reset_working_memory(chat.id)
    assert reset.working_memory.is_empty
    assert reset.working_memory.status == "active"


@pytest.mark.asyncio
async def test_long_term_add_delete_duplicate(tmp_path):
    repository = repo(tmp_path)
    chat = await repository.create_chat()
    entry = await repository.add_long_term_entry("profile", "Науруз", chat.id)

    assert (await repository.get_long_term()).profile[0].text == "Науруз"
    with pytest.raises(CandidateConflict):
        await repository.add_long_term_entry("profile", "Науруз", chat.id)

    await repository.delete_long_term_entry("profile", entry.id)
    assert (await repository.get_long_term()).total_count() == 0
    with pytest.raises(LongTermEntryNotFound):
        await repository.delete_long_term_entry("profile", "missing")


@pytest.mark.asyncio
async def test_candidates_flow_approve_reject_and_dedup(tmp_path):
    repository = repo(tmp_path)
    chat = await repository.create_chat()
    await repository.add_candidates(
        [
            {"text": "аллергия", "category": "knowledge"},
            {"text": "аллергия", "category": "knowledge"},
            {"text": "Kotlin", "category": "profile"},
        ],
        chat.id,
    )
    pending = await repository.list_candidates("pending")
    assert [c.text for c in pending] == ["аллергия", "Kotlin"]

    entry = await repository.approve_candidate(pending[0].id)
    assert entry.text == "аллергия"
    assert (await repository.get_long_term()).knowledge[0].text == "аллергия"
    with pytest.raises(CandidateConflict):
        await repository.approve_candidate(pending[0].id)

    await repository.reject_candidate(pending[1].id)
    assert [c.text for c in await repository.list_candidates("pending")] == []
    assert await repository.clear_rejected_candidates() == 1
    with pytest.raises(CandidateNotFound):
        await repository.reject_candidate("missing")


@pytest.mark.asyncio
async def test_malformed_chat_file_raises_persistence_error(tmp_path):
    repository = repo(tmp_path)
    chat = await repository.create_chat()
    (tmp_path / "chats" / f"{chat.id}.json").write_text("not-json")

    with pytest.raises(ChatPersistenceError):
        await repository.get_chat(chat.id)
```

- [ ] **Step 2: Запустить тест — должен упасть**

Run: `cd day11/backend && python -m pytest tests/test_memory_repository.py -q`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Написать репозиторий**

Create `day11/backend/app/infrastructure/json_memory_repository.py`:
```python
import asyncio
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.domain.models import (
    LONG_TERM_CATEGORIES,
    CandidateConflict,
    CandidateNotFound,
    Chat,
    ChatMessage,
    ChatNotFound,
    ChatPersistenceError,
    ChatSummary,
    LongTermEntry,
    LongTermEntryNotFound,
    LongTermMemory,
    MemoryCandidate,
    TokenUsage,
    WorkingMemory,
)


class JsonMemoryRepository:
    def __init__(
        self, chats_dir: Path, long_term_path: Path, candidates_path: Path
    ):
        self._chats_dir = chats_dir
        self._long_term_path = long_term_path
        self._candidates_path = candidates_path
        self._lock = asyncio.Lock()

    async def create_chat(self, title: str = "Новый чат") -> Chat:
        async with self._lock:
            now = _now()
            chat = Chat(
                id=str(uuid.uuid4()), title=title, created_at=now, updated_at=now
            )
            self._save_chat(chat)
            return chat

    async def list_chats(self) -> list[ChatSummary]:
        async with self._lock:
            summaries = []
            for path in sorted(self._chats_dir.glob("*.json")):
                chat = _chat_from_dict(self._read_json(path))
                summaries.append(
                    ChatSummary(
                        id=chat.id,
                        title=chat.title,
                        created_at=chat.created_at,
                        updated_at=chat.updated_at,
                    )
                )
            return summaries

    async def get_chat(self, chat_id: str) -> Chat:
        async with self._lock:
            return self._read_chat(chat_id)

    async def delete_chat(self, chat_id: str) -> None:
        async with self._lock:
            path = self._chat_path(chat_id)
            if not path.exists():
                raise ChatNotFound(chat_id)
            path.unlink()

    async def append_exchange(
        self,
        chat_id: str,
        user_content: str,
        assistant_content: str,
        usage: TokenUsage,
    ) -> Chat:
        async with self._lock:
            chat = self._read_chat(chat_id)
            if chat.title == "Новый чат" and not chat.messages:
                chat.title = _chat_title(user_content)
            chat.messages.extend(
                [
                    ChatMessage(role="user", content=user_content),
                    ChatMessage(
                        role="assistant", content=assistant_content, usage=usage
                    ),
                ]
            )
            return self._save_chat(chat)

    async def clear_messages(self, chat_id: str) -> Chat:
        async with self._lock:
            chat = self._read_chat(chat_id)
            chat.messages = []
            return self._save_chat(chat)

    async def get_working_memory(self, chat_id: str) -> WorkingMemory:
        async with self._lock:
            return self._read_chat(chat_id).working_memory

    async def save_working_memory(
        self, chat_id: str, working: WorkingMemory
    ) -> Chat:
        async with self._lock:
            chat = self._read_chat(chat_id)
            chat.working_memory = working
            return self._save_chat(chat)

    async def complete_working_memory(self, chat_id: str) -> Chat:
        async with self._lock:
            chat = self._read_chat(chat_id)
            chat.working_memory.status = "done"
            return self._save_chat(chat)

    async def reset_working_memory(self, chat_id: str) -> Chat:
        async with self._lock:
            chat = self._read_chat(chat_id)
            chat.working_memory = WorkingMemory()
            return self._save_chat(chat)

    async def get_long_term(self) -> LongTermMemory:
        async with self._lock:
            return self._read_long_term()

    async def replace_long_term(self, long_term: LongTermMemory) -> LongTermMemory:
        async with self._lock:
            self._write_long_term(long_term)
            return long_term

    async def add_long_term_entry(
        self, category: str, text: str, source_chat_id: str
    ) -> LongTermEntry:
        async with self._lock:
            long_term = self._read_long_term()
            entries = long_term.entries(category)
            if any(item.text == text for item in entries):
                raise CandidateConflict(text)
            entry = LongTermEntry(
                id=str(uuid.uuid4()),
                text=text,
                source_chat_id=source_chat_id,
                created_at=_now(),
            )
            entries.append(entry)
            self._write_long_term(long_term)
            return entry

    async def delete_long_term_entry(self, category: str, entry_id: str) -> None:
        async with self._lock:
            long_term = self._read_long_term()
            entries = long_term.entries(category)
            remaining = [item for item in entries if item.id != entry_id]
            if len(remaining) == len(entries):
                raise LongTermEntryNotFound(entry_id)
            setattr(long_term, category, remaining)
            self._write_long_term(long_term)

    async def add_candidates(
        self, items: list[dict], source_chat_id: str
    ) -> list[MemoryCandidate]:
        async with self._lock:
            store = self._read_candidates()
            pending_texts = {
                item["text"]
                for item in store["candidates"]
                if item["status"] == "pending"
            }
            created = []
            for item in items:
                if item["text"] in pending_texts:
                    continue
                candidate = MemoryCandidate(
                    id=str(uuid.uuid4()),
                    text=item["text"],
                    category=item["category"],
                    source_chat_id=source_chat_id,
                    created_at=_now(),
                )
                store["candidates"].append(_candidate_to_dict(candidate))
                pending_texts.add(item["text"])
                created.append(candidate)
            self._write_candidates(store)
            return created

    async def list_candidates(self, status: str | None = "pending") -> list[MemoryCandidate]:
        async with self._lock:
            store = self._read_candidates()
            return [
                _candidate_from_dict(item)
                for item in store["candidates"]
                if status is None or item["status"] == status
            ]

    async def approve_candidate(self, candidate_id: str) -> LongTermEntry:
        async with self._lock:
            store = self._read_candidates()
            candidate = _find_candidate(store, candidate_id)
            if candidate.status != "pending":
                raise CandidateConflict(candidate_id)
            long_term = self._read_long_term()
            entries = long_term.entries(candidate.category)
            if any(item.text == candidate.text for item in entries):
                raise CandidateConflict(candidate.text)
            entry = LongTermEntry(
                id=str(uuid.uuid4()),
                text=candidate.text,
                source_chat_id=candidate.source_chat_id,
                created_at=_now(),
            )
            entries.append(entry)
            self._write_long_term(long_term)
            candidate.status = "approved"
            self._write_candidates(store)
            return entry

    async def reject_candidate(self, candidate_id: str) -> MemoryCandidate:
        async with self._lock:
            store = self._read_candidates()
            candidate = _find_candidate(store, candidate_id)
            if candidate.status != "pending":
                raise CandidateConflict(candidate_id)
            candidate.status = "rejected"
            self._write_candidates(store)
            return candidate

    async def clear_rejected_candidates(self) -> int:
        async with self._lock:
            store = self._read_candidates()
            kept = [
                item for item in store["candidates"] if item["status"] != "rejected"
            ]
            removed = len(store["candidates"]) - len(kept)
            store["candidates"] = kept
            self._write_candidates(store)
            return removed

    def _chat_path(self, chat_id: str) -> Path:
        return self._chats_dir / f"{chat_id}.json"

    def _read_chat(self, chat_id: str) -> Chat:
        path = self._chat_path(chat_id)
        if not path.exists():
            raise ChatNotFound(chat_id)
        return _chat_from_dict(self._read_json(path))

    def _save_chat(self, chat: Chat) -> Chat:
        chat.updated_at = _now()
        self._write_json(self._chat_path(chat.id), _chat_to_dict(chat))
        return chat

    def _read_long_term(self) -> LongTermMemory:
        if not self._long_term_path.exists():
            return LongTermMemory()
        payload = self._read_json(self._long_term_path)
        return LongTermMemory(
            profile=[_entry_from_dict(item) for item in payload.get("profile", [])],
            decisions=[_entry_from_dict(item) for item in payload.get("decisions", [])],
            knowledge=[_entry_from_dict(item) for item in payload.get("knowledge", [])],
        )

    def _write_long_term(self, long_term: LongTermMemory) -> None:
        self._write_json(
            self._long_term_path,
            {
                "version": 1,
                "profile": [_entry_to_dict(item) for item in long_term.profile],
                "decisions": [_entry_to_dict(item) for item in long_term.decisions],
                "knowledge": [_entry_to_dict(item) for item in long_term.knowledge],
            },
        )

    def _read_candidates(self) -> dict:
        if not self._candidates_path.exists():
            return {"version": 1, "candidates": []}
        return self._read_json(self._candidates_path)

    def _write_candidates(self, store: dict) -> None:
        self._write_json(self._candidates_path, store)

    def _read_json(self, path: Path) -> dict:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ChatPersistenceError(f"Cannot read {path.name}") from error
        if not isinstance(payload, dict):
            raise ChatPersistenceError(f"Invalid format in {path.name}")
        return payload

    def _write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                delete=False,
            ) as temporary:
                json.dump(payload, temporary, ensure_ascii=False, indent=2)
                temporary.write("\n")
                temp_path = temporary.name
            os.replace(temp_path, path)
        except OSError as error:
            if temp_path:
                Path(temp_path).unlink(missing_ok=True)
            raise ChatPersistenceError(f"Cannot write {path.name}") from error


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _chat_title(content: str) -> str:
    compact = " ".join(content.split())
    if not compact:
        return "Новый чат"
    max_length = 40
    if len(compact) <= max_length:
        return compact
    words: list[str] = []
    for word in compact.split():
        candidate = " ".join([*words, word])
        if len(candidate) >= max_length:
            break
        words.append(word)
    title = " ".join(words).rstrip(".,;:!?")
    return f"{title}…" or "Новый чат"


def _find_candidate(store: dict, candidate_id: str) -> MemoryCandidate:
    for item in store["candidates"]:
        if item["id"] == candidate_id:
            return _candidate_from_dict(item)
    raise CandidateNotFound(candidate_id)


def _working_to_dict(working: WorkingMemory) -> dict:
    return {
        "goal": working.goal,
        "constraints": list(working.constraints),
        "decisions": list(working.decisions),
        "status": working.status,
    }


def _working_from_dict(payload: dict | None) -> WorkingMemory:
    payload = payload or {}
    return WorkingMemory(
        goal=payload.get("goal", ""),
        constraints=list(payload.get("constraints", [])),
        decisions=list(payload.get("decisions", [])),
        status=payload.get("status", "active"),
    )


def _message_to_dict(message: ChatMessage) -> dict:
    stored = {"role": message.role, "content": message.content}
    if message.usage is not None:
        stored["usage"] = {
            "prompt_tokens": message.usage.prompt_tokens,
            "completion_tokens": message.usage.completion_tokens,
            "total_tokens": message.usage.total_tokens,
        }
    return stored


def _message_from_dict(message: dict) -> ChatMessage:
    usage = message.get("usage")
    return ChatMessage(
        role=message["role"],
        content=message["content"],
        usage=TokenUsage(**usage) if usage else None,
    )


def _chat_to_dict(chat: Chat) -> dict:
    return {
        "id": chat.id,
        "title": chat.title,
        "created_at": chat.created_at,
        "updated_at": chat.updated_at,
        "working_memory": _working_to_dict(chat.working_memory),
        "messages": [_message_to_dict(message) for message in chat.messages],
    }


def _chat_from_dict(payload: dict) -> Chat:
    return Chat(
        id=payload["id"],
        title=payload["title"],
        created_at=payload["created_at"],
        updated_at=payload["updated_at"],
        messages=[_message_from_dict(item) for item in payload.get("messages", [])],
        working_memory=_working_from_dict(payload.get("working_memory")),
    )


def _entry_to_dict(entry: LongTermEntry) -> dict:
    return {
        "id": entry.id,
        "text": entry.text,
        "source_chat_id": entry.source_chat_id,
        "created_at": entry.created_at,
    }


def _entry_from_dict(payload: dict) -> LongTermEntry:
    return LongTermEntry(
        id=payload["id"],
        text=payload["text"],
        source_chat_id=payload.get("source_chat_id", ""),
        created_at=payload.get("created_at", ""),
    )


def _candidate_to_dict(candidate: MemoryCandidate) -> dict:
    return {
        "id": candidate.id,
        "text": candidate.text,
        "category": candidate.category,
        "source_chat_id": candidate.source_chat_id,
        "status": candidate.status,
        "created_at": candidate.created_at,
    }


def _candidate_from_dict(payload: dict) -> MemoryCandidate:
    return MemoryCandidate(
        id=payload["id"],
        text=payload["text"],
        category=payload["category"],
        source_chat_id=payload.get("source_chat_id", ""),
        status=payload.get("status", "pending"),
        created_at=payload.get("created_at", ""),
    )
```

- [ ] **Step 4: Запустить тест — должен пройти**

Run: `cd day11/backend && python -m pytest tests/test_memory_repository.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add day11/backend/app/infrastructure/json_memory_repository.py day11/backend/tests/test_memory_repository.py
git commit -m "feat(day11): separate-storage JSON memory repository"
```

---

### Task 5: Поток агента

**Files:**
- Create: `day11/backend/app/application/agent.py`
- Modify: `day11/backend/app/application/usage.py` (без изменений логики; используется как есть)
- Test: `day11/backend/tests/test_agent_memory.py`

**Interfaces:**
- Consumes: `memory.py` (Task 3), модели (Task 2), `usage.build_dialog_usage`, `ports.llm_gateway.LLMGateway`, `ports.token_counter.TokenCounter`.
- Produces: `SYSTEM_PROMPT: str`, `MAX_MESSAGE_LENGTH = 4000`, `Agent(gateway, repository, counter, config, model="deepseek-chat", candidates_enabled=True)` с `async run(chat_id, user_text) -> AgentResult`.
- Поведение: команда `запомни:` пишет сразу (через `parse_memory_command` + `parse_command_category`), без поиска кандидатов; иначе после ответа — поиск кандидатов и `add_candidates`.

- [ ] **Step 1: Написать падающий тест**

Create `day11/backend/tests/test_agent_memory.py`:
```python
import pytest

from app.application.agent import Agent
from app.domain.models import (
    Chat,
    ChatMessage,
    InvalidUserMessage,
    LLMResponse,
    LongTermMemory,
    TokenUsage,
    UsageConfig,
    WorkingMemory,
)
from app.infrastructure.token_counter import TiktokenCounter


def usage(prompt=30, completion=5):
    return TokenUsage(prompt, completion, prompt + completion)


class ScriptedGateway:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def complete(self, messages):
        self.calls.append(list(messages))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def response(text="ok", prompt=30, completion=5):
    return LLMResponse(text, "m", usage(prompt, completion))


class MemoryRepository:
    def __init__(self, chat):
        self.chat = chat
        self.long_term = LongTermMemory()
        self.appended = []
        self.candidates = []
        self.entries = []

    async def get_chat(self, chat_id):
        return self.chat

    async def get_long_term(self):
        return self.long_term

    async def append_exchange(self, chat_id, user, assistant, token_usage):
        self.appended.append((user, assistant))
        self.chat.messages.extend(
            [
                ChatMessage(role="user", content=user),
                ChatMessage(role="assistant", content=assistant, usage=token_usage),
            ]
        )
        return self.chat

    async def add_long_term_entry(self, category, text, source_chat_id):
        self.entries.append((category, text))

    async def add_candidates(self, items, source_chat_id):
        self.candidates.append(items)


def make_agent(gateway, repository, config=None, candidates_enabled=True):
    return Agent(
        gateway,
        repository=repository,
        counter=TiktokenCounter(),
        config=config or UsageConfig(),
        candidates_enabled=candidates_enabled,
    )


def sample_chat(working=None):
    return Chat(
        id="c1",
        title="T",
        created_at="a",
        updated_at="b",
        messages=[ChatMessage(role="user", content="привет")],
        working_memory=working or WorkingMemory(),
    )


@pytest.mark.asyncio
async def test_prompt_contains_all_three_layers():
    repository = MemoryRepository(sample_chat(WorkingMemory(goal="Собрать ТЗ")))
    repository.long_term = LongTermMemory()
    gateway = ScriptedGateway([response(), response("[]")])

    await make_agent(gateway, repository).run("c1", "вопрос")

    main_call = gateway.calls[0]
    contents = [m.content for m in main_call]
    assert any("## Рабочая память" in c for c in contents)
    assert any("привет" in c for c in contents)
    assert main_call[-1].content == "вопрос"


@pytest.mark.asyncio
async def test_candidates_are_searched_after_answer():
    repository = MemoryRepository(sample_chat())
    gateway = ScriptedGateway(
        [
            response("ответ"),
            response('[{"text": "аллергия", "category": "knowledge"}]'),
        ]
    )

    await make_agent(gateway, repository).run("c1", "я аллергик")

    assert len(gateway.calls) == 2
    assert repository.candidates == [
        [{"text": "аллергия", "category": "knowledge"}]
    ]
    assert repository.appended == [("я аллергик", "ответ")]


@pytest.mark.asyncio
async def test_memory_command_writes_immediately_without_candidates():
    repository = MemoryRepository(sample_chat())
    gateway = ScriptedGateway(
        [
            response('[{"text": "люблю Kotlin", "category": "profile"}]'),
            response("ок"),
        ]
    )

    result = await make_agent(gateway, repository).run(
        "c1", "запомни: люблю Kotlin"
    )

    assert repository.entries == [("profile", "люблю Kotlin")]
    assert repository.candidates == []
    assert result.answer == "ок"


@pytest.mark.asyncio
async def test_candidates_disabled_skips_second_call():
    repository = MemoryRepository(sample_chat())
    gateway = ScriptedGateway([response("ответ")])

    await make_agent(gateway, repository, candidates_enabled=False).run(
        "c1", "привет"
    )

    assert len(gateway.calls) == 1


@pytest.mark.asyncio
async def test_blank_message_rejected():
    with pytest.raises(InvalidUserMessage):
        await make_agent(
            ScriptedGateway([]), MemoryRepository(sample_chat())
        ).run("c1", "   ")
```

- [ ] **Step 2: Запустить тест — должен упасть**

Run: `cd day11/backend && python -m pytest tests/test_agent_memory.py -q`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Написать agent.py**

Create `day11/backend/app/application/agent.py`:
```python
from time import perf_counter

from app.application.memory import (
    build_candidate_messages,
    build_long_term_block,
    build_prompt,
    build_working_block,
    parse_candidates,
    parse_command_category,
    parse_memory_command,
)
from app.application.ports.chat_repository import ChatRepository
from app.application.ports.llm_gateway import LLMGateway
from app.application.ports.token_counter import TokenCounter
from app.application.usage import build_dialog_usage, exchange_cost_usd
from app.domain.models import (
    AgentResult,
    AgentStage,
    CandidateConflict,
    ChatMessage,
    ContextLimitExceeded,
    InvalidUserMessage,
    MemoryInfo,
    UsageConfig,
    UsageReport,
)


SYSTEM_PROMPT = (
    "You are a helpful assistant. Answer in the same language as the user. "
    "Be concise, clear, and complete. Never reveal private hidden chain-of-thought; "
    "give a short useful summary instead if the user asks how you reasoned."
)
MAX_MESSAGE_LENGTH = 4000
CANDIDATE_LIMIT = 5


class Agent:
    def __init__(
        self,
        gateway: LLMGateway,
        repository: ChatRepository,
        counter: TokenCounter,
        config: UsageConfig,
        model: str = "deepseek-chat",
        candidates_enabled: bool = True,
    ):
        self._gateway = gateway
        self._repository = repository
        self._counter = counter
        self._config = config
        self._model = model
        self._candidates_enabled = candidates_enabled

    @staticmethod
    def _validate_message(user_text: str) -> str:
        if not isinstance(user_text, str):
            raise InvalidUserMessage("Message must be a string")
        message = user_text.strip()
        if not message:
            raise InvalidUserMessage("Message cannot be blank")
        if len(message) > MAX_MESSAGE_LENGTH:
            raise InvalidUserMessage(
                f"Message must be shorter than {MAX_MESSAGE_LENGTH} characters"
            )
        return message

    async def run(self, chat_id: str, user_text: str) -> AgentResult:
        message = self._validate_message(user_text)
        chat = await self._repository.get_chat(chat_id)
        long_term = await self._repository.get_long_term()

        command_text = parse_memory_command(message)
        command_tokens = 0
        if command_text is not None:
            if not command_text:
                raise InvalidUserMessage("Memory command is empty")
            classification = await self._gateway.complete(
                build_candidate_messages(command_text, "", long_term, 1)
            )
            command_tokens = classification.usage.total_tokens
            category = parse_command_category(classification.text)
            try:
                await self._repository.add_long_term_entry(
                    category, command_text, chat_id
                )
            except CandidateConflict:
                pass
            long_term = await self._repository.get_long_term()

        new_message = ChatMessage(role="user", content=message)
        prompt = build_prompt(chat, long_term, SYSTEM_PROMPT)
        call_messages = [*prompt, new_message]
        request_tokens = self._counter.count_messages([new_message])
        sent_history_tokens = self._counter.count_messages(call_messages) - request_tokens
        if sent_history_tokens + request_tokens > self._config.context_limit_tokens:
            raise ContextLimitExceeded(
                sent_history_tokens + request_tokens,
                self._config.context_limit_tokens,
            )

        started_at = perf_counter()
        response = await self._gateway.complete(call_messages)
        answer = response.text.strip()
        updated_chat = await self._repository.append_exchange(
            chat_id, message, answer, response.usage
        )

        candidate_tokens = 0
        if command_text is None and self._candidates_enabled:
            extraction = await self._gateway.complete(
                build_candidate_messages(message, answer, long_term, CANDIDATE_LIMIT)
            )
            candidate_tokens = extraction.usage.total_tokens
            candidates = parse_candidates(extraction.text, CANDIDATE_LIMIT)
            if candidates:
                await self._repository.add_candidates(candidates, chat_id)

        system_message = ChatMessage(role="system", content=SYSTEM_PROMPT)
        dialog = build_dialog_usage(
            [system_message, *updated_chat.messages], self._counter, self._config
        )
        long_term_block = build_long_term_block(long_term)
        working_block = build_working_block(updated_chat.working_memory)
        return AgentResult(
            answer=answer,
            model=response.model or self._model,
            duration_ms=round((perf_counter() - started_at) * 1000),
            stages=[
                AgentStage(name="UI", status="completed"),
                AgentStage(name="Agent", status="completed"),
                AgentStage(name="DeepSeek API", status="completed"),
            ],
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
                memory=MemoryInfo(
                    long_term_count=long_term.total_count(),
                    long_term_tokens=(
                        self._counter.count_messages([long_term_block])
                        if long_term_block
                        else 0
                    ),
                    working_tokens=(
                        self._counter.count_messages([working_block])
                        if working_block
                        else 0
                    ),
                    history_tokens=self._counter.count_messages(updated_chat.messages),
                    candidate_tokens=candidate_tokens + command_tokens,
                ),
            ),
        )
```

- [ ] **Step 4: Обновить порт репозитория под новый интерфейс**

Replace `day11/backend/app/application/ports/chat_repository.py`:
```python
from typing import Protocol

from app.domain.models import (
    Chat,
    ChatSummary,
    LongTermEntry,
    LongTermMemory,
    MemoryCandidate,
    TokenUsage,
    WorkingMemory,
)


class ChatRepository(Protocol):
    async def create_chat(self, title: str = "Новый чат") -> Chat: ...

    async def list_chats(self) -> list[ChatSummary]: ...

    async def get_chat(self, chat_id: str) -> Chat: ...

    async def delete_chat(self, chat_id: str) -> None: ...

    async def append_exchange(
        self,
        chat_id: str,
        user_content: str,
        assistant_content: str,
        usage: TokenUsage,
    ) -> Chat: ...

    async def clear_messages(self, chat_id: str) -> Chat: ...

    async def get_working_memory(self, chat_id: str) -> WorkingMemory: ...

    async def save_working_memory(
        self, chat_id: str, working: WorkingMemory
    ) -> Chat: ...

    async def complete_working_memory(self, chat_id: str) -> Chat: ...

    async def reset_working_memory(self, chat_id: str) -> Chat: ...

    async def get_long_term(self) -> LongTermMemory: ...

    async def replace_long_term(self, long_term: LongTermMemory) -> LongTermMemory: ...

    async def add_long_term_entry(
        self, category: str, text: str, source_chat_id: str
    ) -> LongTermEntry: ...

    async def delete_long_term_entry(self, category: str, entry_id: str) -> None: ...

    async def add_candidates(
        self, items: list[dict], source_chat_id: str
    ) -> list[MemoryCandidate]: ...

    async def list_candidates(
        self, status: str | None = "pending"
    ) -> list[MemoryCandidate]: ...

    async def approve_candidate(self, candidate_id: str) -> LongTermEntry: ...

    async def reject_candidate(self, candidate_id: str) -> MemoryCandidate: ...

    async def clear_rejected_candidates(self) -> int: ...
```

- [ ] **Step 5: Запустить тесты — должны пройти**

Run: `cd day11/backend && python -m pytest tests/test_agent_memory.py tests/test_memory.py tests/test_models.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add day11/backend/app/application/agent.py day11/backend/app/application/ports/chat_repository.py day11/backend/tests/test_agent_memory.py
git commit -m "feat(day11): agent reads/writes three memory layers"
```

---

### Task 6: HTTP API

**Files:**
- Modify: `day11/backend/app/infrastructure/settings.py`
- Create: `day11/backend/app/presentation/schemas.py`
- Create: `day11/backend/app/presentation/dependencies.py`
- Create: `day11/backend/app/presentation/routes.py`
- Modify: `day11/backend/app/main.py`
- Test: `day11/backend/tests/test_memory_api.py`
- Modify: `day11/backend/.env.example`

**Interfaces:**
- Consumes: `Agent`, `JsonMemoryRepository`, модели, `memory.SYSTEM_PROMPT`.
- Produces endpoints:
  - `POST /api/chats` · `GET /api/chats` · `GET /api/chats/{id}` · `DELETE /api/chats/{id}`
  - `DELETE /api/chats/{id}/messages`
  - `GET|PUT /api/chats/{id}/working-memory`
  - `POST /api/chats/{id}/working-memory/complete` · `.../reset`
  - `GET|PUT /api/long-term` · `DELETE /api/long-term/{category}/{entry_id}`
  - `GET /api/candidates?status=pending` · `POST /api/candidates/{id}/approve` · `POST /api/candidates/{id}/reject` · `DELETE /api/candidates?status=rejected`
  - `POST /api/chats/{id}/messages {message}` → `{chat_id, answer, model, duration_ms, stages, usage}`

- [ ] **Step 1: Обновить settings.py**

Replace `day11/backend/app/infrastructure/settings.py`:
```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    deepseek_api_key: str
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    chats_dir: str = "data/chats"
    long_term_file: str = "data/long_term.json"
    candidates_file: str = "data/candidates.json"
    context_limit_tokens: int = 8000
    input_price_per_million: float = 0.30
    output_price_per_million: float = 1.20
    long_term_max_per_category: int = 50
    long_term_max_item_chars: int = 500
    candidates_enabled: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
```

- [ ] **Step 2: Написать падающий API-тест**

Create `day11/backend/tests/test_memory_api.py`:
```python
import json

import pytest
from fastapi.testclient import TestClient

from app.domain.models import (
    AgentResult,
    AgentStage,
    Chat,
    ChatMessage,
    MemoryInfo,
    TokenUsage,
    UsageReport,
    WorkingMemory,
)
from app.infrastructure.json_memory_repository import JsonMemoryRepository
from app.main import app
from app.presentation.dependencies import get_agent, get_repository


def report():
    return UsageReport(
        request_tokens=5,
        history_tokens=20,
        response_tokens=7,
        prompt_tokens_api=25,
        completion_tokens_api=7,
        total_tokens_api=32,
        dialog_total_tokens=32,
        dialog_cost_usd=0.00001,
        context_limit=8000,
        context_remaining=7975,
        warning=False,
        memory=MemoryInfo(0, 0, 0, 20, 9),
    )


class FakeAgent:
    async def run(self, chat_id, message):
        return AgentResult(
            answer="ответ",
            model="deepseek-chat",
            duration_ms=1,
            stages=[AgentStage(name="Agent", status="completed")],
            usage=report(),
        )


@pytest.fixture
def client(tmp_path):
    repository = JsonMemoryRepository(
        chats_dir=tmp_path / "chats",
        long_term_path=tmp_path / "long_term.json",
        candidates_path=tmp_path / "candidates.json",
    )
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_agent] = lambda: FakeAgent()
    with TestClient(app) as test_client:
        yield test_client, repository
    app.dependency_overrides.clear()


def test_chat_crud_and_clear_history(client):
    http, _ = client
    chat_id = http.post("/api/chats").json()["id"]

    detail = http.get(f"/api/chats/{chat_id}").json()
    assert detail["working_memory"]["status"] == "active"
    assert detail["messages"] == []

    assert http.delete(f"/api/chats/{chat_id}/messages").status_code == 200
    assert http.delete(f"/api/chats/{chat_id}").status_code == 204
    assert http.get(f"/api/chats/{chat_id}").status_code == 404


def test_working_memory_endpoints(client):
    http, _ = client
    chat_id = http.post("/api/chats").json()["id"]

    saved = http.put(
        f"/api/chats/{chat_id}/working-memory",
        json={
            "goal": "Собрать ТЗ",
            "constraints": ["бюджет 900"],
            "decisions": [],
            "status": "active",
        },
    )
    assert saved.status_code == 200
    assert saved.json()["working_memory"]["goal"] == "Собрать ТЗ"

    assert http.post(
        f"/api/chats/{chat_id}/working-memory/complete"
    ).json()["working_memory"]["status"] == "done"
    assert http.post(
        f"/api/chats/{chat_id}/working-memory/reset"
    ).json()["working_memory"]["goal"] == ""


def test_long_term_crud(client):
    http, repository = client
    chat_id = http.post("/api/chats").json()["id"]

    created = http.put(
        "/api/long-term",
        json={
            "profile": [{"id": "e1", "text": "Науруз", "source_chat_id": chat_id, "created_at": "t"}],
            "decisions": [],
            "knowledge": [],
        },
    )
    assert created.status_code == 200
    assert http.get("/api/long-term").json()["profile"][0]["text"] == "Науруз"

    assert http.delete("/api/long-term/profile/e1").status_code == 204
    assert http.delete("/api/long-term/profile/e1").status_code == 404


def test_candidates_approve_reject(client, tmp_path):
    http, repository = client
    chat_id = http.post("/api/chats").json()["id"]

    # Кандидаты заводятся напрямую в файл (отдельного API создания нет).
    (tmp_path / "candidates.json").write_text(
        json.dumps(
            {
                "version": 1,
                "candidates": [
                    {
                        "id": "cand-1",
                        "text": "аллергия",
                        "category": "knowledge",
                        "source_chat_id": chat_id,
                        "status": "pending",
                        "created_at": "t",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    assert len(http.get("/api/candidates?status=pending").json()) == 1
    approved = http.post("/api/candidates/cand-1/approve")
    assert approved.status_code == 200
    assert approved.json()["text"] == "аллергия"
    assert http.get("/api/long-term").json()["knowledge"][0]["text"] == "аллергия"

    assert http.post("/api/candidates/cand-1/reject").status_code == 409


def test_send_message_returns_memory_usage(client):
    http, _ = client
    chat_id = http.post("/api/chats").json()["id"]

    response = http.post(
        f"/api/chats/{chat_id}/messages", json={"message": "привет"}
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "ответ"
    assert response.json()["usage"]["memory"]["candidate_tokens"] == 9
```

- [ ] **Step 3: Запустить тест — должен упасть**

Run: `cd day11/backend && python -m pytest tests/test_memory_api.py -q`
Expected: FAIL (`ModuleNotFoundError` для `app.presentation.routes`/`dependencies`).

- [ ] **Step 4: Написать schemas.py**

Create `day11/backend/app/presentation/schemas.py`:
```python
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.domain.models import StageStatus


class ChatMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)

    @field_validator("message")
    @classmethod
    def message_cannot_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message cannot be blank")
        return value


class StageResponse(BaseModel):
    name: str
    status: StageStatus


class MemoryInfoResponse(BaseModel):
    long_term_count: int
    long_term_tokens: int
    working_tokens: int
    history_tokens: int
    candidate_tokens: int


class UsageResponse(BaseModel):
    request_tokens: int
    history_tokens: int
    response_tokens: int
    prompt_tokens_api: int
    completion_tokens_api: int
    total_tokens_api: int
    dialog_total_tokens: int
    dialog_cost_usd: float
    context_limit: int
    context_remaining: int
    warning: bool
    memory: MemoryInfoResponse | None = None


class ChatResponse(BaseModel):
    chat_id: str
    answer: str
    model: str
    duration_ms: int
    stages: list[StageResponse]
    usage: UsageResponse


class TokenUsageResponse(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatMessageResponse(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    usage: TokenUsageResponse | None = None


class WorkingMemoryResponse(BaseModel):
    goal: str
    constraints: list[str]
    decisions: list[str]
    status: Literal["active", "done"]


class WorkingMemoryRequest(BaseModel):
    goal: str = ""
    constraints: list[str] = []
    decisions: list[str] = []
    status: Literal["active", "done"] = "active"


class LongTermEntryResponse(BaseModel):
    id: str
    text: str
    source_chat_id: str
    created_at: str


class LongTermResponse(BaseModel):
    profile: list[LongTermEntryResponse]
    decisions: list[LongTermEntryResponse]
    knowledge: list[LongTermEntryResponse]


class LongTermEntryRequest(BaseModel):
    id: str
    text: str
    source_chat_id: str = ""
    created_at: str = ""


class LongTermRequest(BaseModel):
    profile: list[LongTermEntryRequest] = []
    decisions: list[LongTermEntryRequest] = []
    knowledge: list[LongTermEntryRequest] = []


class CandidateResponse(BaseModel):
    id: str
    text: str
    category: str
    source_chat_id: str
    status: str
    created_at: str


class DialogUsageResponse(BaseModel):
    history_tokens: int
    dialog_total_tokens: int
    dialog_cost_usd: float
    context_limit: int
    context_remaining: int
    warning: bool


class ChatSummaryResponse(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str


class ChatDetailResponse(ChatSummaryResponse):
    messages: list[ChatMessageResponse]
    working_memory: WorkingMemoryResponse
    dialog_usage: DialogUsageResponse
```

- [ ] **Step 5: Написать dependencies.py**

Create `day11/backend/app/presentation/dependencies.py`:
```python
from functools import lru_cache
from pathlib import Path

from app.application.agent import Agent
from app.application.ports.chat_repository import ChatRepository
from app.domain.models import UsageConfig
from app.infrastructure.deepseek_gateway import DeepSeekGateway
from app.infrastructure.json_memory_repository import JsonMemoryRepository
from app.infrastructure.settings import Settings
from app.infrastructure.token_counter import TiktokenCounter


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_repository() -> JsonMemoryRepository:
    settings = get_settings()
    return JsonMemoryRepository(
        chats_dir=Path(settings.chats_dir),
        long_term_path=Path(settings.long_term_file),
        candidates_path=Path(settings.candidates_file),
    )


@lru_cache
def get_token_counter() -> TiktokenCounter:
    return TiktokenCounter()


@lru_cache
def get_usage_config() -> UsageConfig:
    settings = get_settings()
    return UsageConfig(
        context_limit_tokens=settings.context_limit_tokens,
        input_price_per_million=settings.input_price_per_million,
        output_price_per_million=settings.output_price_per_million,
        long_term_max_per_category=settings.long_term_max_per_category,
        long_term_max_item_chars=settings.long_term_max_item_chars,
    )


def get_agent() -> Agent:
    settings = get_settings()
    gateway = DeepSeekGateway(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
    )
    repository: ChatRepository = get_repository()
    return Agent(
        gateway,
        repository=repository,
        counter=get_token_counter(),
        config=get_usage_config(),
        model=settings.deepseek_model,
        candidates_enabled=settings.candidates_enabled,
    )
```

- [ ] **Step 6: Написать routes.py**

Create `day11/backend/app/presentation/routes.py`:
```python
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.application.agent import SYSTEM_PROMPT, Agent
from app.application.ports.chat_repository import ChatRepository
from app.application.ports.token_counter import TokenCounter
from app.application.usage import build_dialog_usage
from app.domain.models import (
    CandidateConflict,
    CandidateNotFound,
    Chat,
    ChatMessage,
    ChatNotFound,
    ChatSummary,
    LongTermEntryNotFound,
    LongTermMemory,
    UsageConfig,
    UsageReport,
    WorkingMemory,
)
from app.presentation.dependencies import (
    get_agent,
    get_repository,
    get_token_counter,
    get_usage_config,
)
from app.presentation.schemas import (
    CandidateResponse,
    ChatDetailResponse,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatResponse,
    ChatSummaryResponse,
    DialogUsageResponse,
    LongTermEntryResponse,
    LongTermRequest,
    LongTermResponse,
    MemoryInfoResponse,
    StageResponse,
    TokenUsageResponse,
    UsageResponse,
    WorkingMemoryRequest,
    WorkingMemoryResponse,
)


router = APIRouter()


@router.post("/api/chats", response_model=ChatSummaryResponse, status_code=201)
async def create_chat(
    repository: Annotated[ChatRepository, Depends(get_repository)],
) -> ChatSummaryResponse:
    return _summary_response(await repository.create_chat())


@router.get("/api/chats", response_model=list[ChatSummaryResponse])
async def list_chats(
    repository: Annotated[ChatRepository, Depends(get_repository)],
) -> list[ChatSummaryResponse]:
    return [_summary_response(chat) for chat in await repository.list_chats()]


@router.get("/api/chats/{chat_id}", response_model=ChatDetailResponse)
async def get_chat(
    chat_id: str,
    repository: Annotated[ChatRepository, Depends(get_repository)],
    counter: Annotated[TokenCounter, Depends(get_token_counter)],
    config: Annotated[UsageConfig, Depends(get_usage_config)],
) -> ChatDetailResponse:
    chat = await repository.get_chat(chat_id)
    return _detail_response(chat, counter, config)


@router.delete("/api/chats/{chat_id}", status_code=204)
async def delete_chat(
    chat_id: str,
    repository: Annotated[ChatRepository, Depends(get_repository)],
) -> Response:
    await repository.delete_chat(chat_id)
    return Response(status_code=204)


@router.delete("/api/chats/{chat_id}/messages", response_model=ChatDetailResponse)
async def clear_history(
    chat_id: str,
    repository: Annotated[ChatRepository, Depends(get_repository)],
    counter: Annotated[TokenCounter, Depends(get_token_counter)],
    config: Annotated[UsageConfig, Depends(get_usage_config)],
) -> ChatDetailResponse:
    chat = await repository.clear_messages(chat_id)
    return _detail_response(chat, counter, config)


@router.get(
    "/api/chats/{chat_id}/working-memory",
    response_model=WorkingMemoryResponse,
)
async def get_working_memory(
    chat_id: str,
    repository: Annotated[ChatRepository, Depends(get_repository)],
) -> WorkingMemoryResponse:
    working = await repository.get_working_memory(chat_id)
    return WorkingMemoryResponse(**_working_dict(working))


@router.put(
    "/api/chats/{chat_id}/working-memory",
    response_model=ChatDetailResponse,
)
async def save_working_memory(
    chat_id: str,
    request: WorkingMemoryRequest,
    repository: Annotated[ChatRepository, Depends(get_repository)],
    counter: Annotated[TokenCounter, Depends(get_token_counter)],
    config: Annotated[UsageConfig, Depends(get_usage_config)],
) -> ChatDetailResponse:
    working = WorkingMemory(
        goal=request.goal,
        constraints=list(request.constraints),
        decisions=list(request.decisions),
        status=request.status,
    )
    chat = await repository.save_working_memory(chat_id, working)
    return _detail_response(chat, counter, config)


@router.post(
    "/api/chats/{chat_id}/working-memory/complete",
    response_model=ChatDetailResponse,
)
async def complete_working_memory(
    chat_id: str,
    repository: Annotated[ChatRepository, Depends(get_repository)],
    counter: Annotated[TokenCounter, Depends(get_token_counter)],
    config: Annotated[UsageConfig, Depends(get_usage_config)],
) -> ChatDetailResponse:
    chat = await repository.complete_working_memory(chat_id)
    return _detail_response(chat, counter, config)


@router.post(
    "/api/chats/{chat_id}/working-memory/reset",
    response_model=ChatDetailResponse,
)
async def reset_working_memory(
    chat_id: str,
    repository: Annotated[ChatRepository, Depends(get_repository)],
    counter: Annotated[TokenCounter, Depends(get_token_counter)],
    config: Annotated[UsageConfig, Depends(get_usage_config)],
) -> ChatDetailResponse:
    chat = await repository.reset_working_memory(chat_id)
    return _detail_response(chat, counter, config)


@router.get("/api/long-term", response_model=LongTermResponse)
async def get_long_term(
    repository: Annotated[ChatRepository, Depends(get_repository)],
) -> LongTermResponse:
    return _long_term_response(await repository.get_long_term())


@router.put("/api/long-term", response_model=LongTermResponse)
async def replace_long_term(
    request: LongTermRequest,
    repository: Annotated[ChatRepository, Depends(get_repository)],
    config: Annotated[UsageConfig, Depends(get_usage_config)],
) -> LongTermResponse:
    for category in ("profile", "decisions", "knowledge"):
        entries = getattr(request, category)
        if len(entries) > config.long_term_max_per_category:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Категория {category} превышает лимит "
                    f"{config.long_term_max_per_category} записей."
                ),
            )
        for entry in entries:
            if len(entry.text) > config.long_term_max_item_chars:
                raise HTTPException(
                    status_code=400,
                    detail="Запись долговременной памяти слишком длинная.",
                )
    from app.domain.models import LongTermEntry

    long_term = LongTermMemory(
        profile=[LongTermEntry(**entry.model_dump()) for entry in request.profile],
        decisions=[
            LongTermEntry(**entry.model_dump()) for entry in request.decisions
        ],
        knowledge=[
            LongTermEntry(**entry.model_dump()) for entry in request.knowledge
        ],
    )
    return _long_term_response(await repository.replace_long_term(long_term))


@router.delete(
    "/api/long-term/{category}/{entry_id}",
    status_code=204,
)
async def delete_long_term_entry(
    category: str,
    entry_id: str,
    repository: Annotated[ChatRepository, Depends(get_repository)],
) -> Response:
    if category not in ("profile", "decisions", "knowledge"):
        raise HTTPException(status_code=404, detail="Unknown memory category")
    try:
        await repository.delete_long_term_entry(category, entry_id)
    except LongTermEntryNotFound as error:
        raise HTTPException(
            status_code=404, detail="Memory entry not found"
        ) from error
    return Response(status_code=204)


@router.get("/api/candidates", response_model=list[CandidateResponse])
async def list_candidates(
    repository: Annotated[ChatRepository, Depends(get_repository)],
    status: str | None = Query(default="pending"),
) -> list[CandidateResponse]:
    return [
        CandidateResponse(**vars(candidate))
        for candidate in await repository.list_candidates(status)
    ]


@router.post(
    "/api/candidates/{candidate_id}/approve",
    response_model=LongTermEntryResponse,
)
async def approve_candidate(
    candidate_id: str,
    repository: Annotated[ChatRepository, Depends(get_repository)],
) -> LongTermEntryResponse:
    try:
        entry = await repository.approve_candidate(candidate_id)
    except CandidateNotFound as error:
        raise HTTPException(
            status_code=404, detail="Candidate not found"
        ) from error
    except CandidateConflict as error:
        raise HTTPException(
            status_code=409, detail="Candidate already resolved or duplicated"
        ) from error
    return LongTermEntryResponse(**vars(entry))


@router.post(
    "/api/candidates/{candidate_id}/reject",
    response_model=CandidateResponse,
)
async def reject_candidate(
    candidate_id: str,
    repository: Annotated[ChatRepository, Depends(get_repository)],
) -> CandidateResponse:
    try:
        candidate = await repository.reject_candidate(candidate_id)
    except CandidateNotFound as error:
        raise HTTPException(
            status_code=404, detail="Candidate not found"
        ) from error
    except CandidateConflict as error:
        raise HTTPException(
            status_code=409, detail="Candidate already resolved"
        ) from error
    return CandidateResponse(**vars(candidate))


@router.delete("/api/candidates", status_code=200)
async def clear_rejected_candidates(
    repository: Annotated[ChatRepository, Depends(get_repository)],
    status: str = Query(default="rejected"),
) -> dict:
    if status != "rejected":
        raise HTTPException(status_code=400, detail="Only rejected can be cleared")
    removed = await repository.clear_rejected_candidates()
    return {"removed": removed}


@router.post("/api/chats/{chat_id}/messages", response_model=ChatResponse)
async def send_message(
    chat_id: str,
    request: ChatMessageRequest,
    agent: Annotated[Agent, Depends(get_agent)],
) -> ChatResponse:
    result = await agent.run(chat_id, request.message)
    return ChatResponse(
        chat_id=chat_id,
        answer=result.answer,
        model=result.model,
        duration_ms=result.duration_ms,
        stages=[
            StageResponse(name=stage.name, status=stage.status)
            for stage in result.stages
        ],
        usage=_usage_response(result.usage),
    )


def _working_dict(working: WorkingMemory) -> dict:
    return {
        "goal": working.goal,
        "constraints": list(working.constraints),
        "decisions": list(working.decisions),
        "status": working.status,
    }


def _summary_response(chat: Chat | ChatSummary) -> ChatSummaryResponse:
    return ChatSummaryResponse(
        id=chat.id,
        title=chat.title,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
    )


def _message_responses(messages) -> list[ChatMessageResponse]:
    return [
        ChatMessageResponse(
            role=message.role,
            content=message.content,
            usage=(
                TokenUsageResponse(
                    prompt_tokens=message.usage.prompt_tokens,
                    completion_tokens=message.usage.completion_tokens,
                    total_tokens=message.usage.total_tokens,
                )
                if message.usage
                else None
            ),
        )
        for message in messages
    ]


def _detail_response(
    chat: Chat, counter: TokenCounter, config: UsageConfig
) -> ChatDetailResponse:
    dialog = build_dialog_usage(
        [ChatMessage(role="system", content=SYSTEM_PROMPT), *chat.messages],
        counter,
        config,
    )
    return ChatDetailResponse(
        **_summary_response(chat).model_dump(),
        messages=_message_responses(chat.messages),
        working_memory=WorkingMemoryResponse(**_working_dict(chat.working_memory)),
        dialog_usage=DialogUsageResponse(**vars(dialog)),
    )


def _long_term_response(long_term: LongTermMemory) -> LongTermResponse:
    def entries(items):
        return [LongTermEntryResponse(**vars(item)) for item in items]

    return LongTermResponse(
        profile=entries(long_term.profile),
        decisions=entries(long_term.decisions),
        knowledge=entries(long_term.knowledge),
    )


def _usage_response(report: UsageReport) -> UsageResponse:
    data = dict(vars(report))
    memory = data.pop("memory")
    return UsageResponse(
        **data,
        memory=MemoryInfoResponse(**vars(memory)) if memory else None,
    )
```

- [ ] **Step 7: Обновить main.py**

Replace `day11/backend/app/main.py`:
```python
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.domain.models import (
    AuthenticationGatewayError,
    ChatNotFound,
    ChatPersistenceError,
    ContextLimitExceeded,
    GatewayTimeoutError,
    InvalidUserMessage,
    LLMGatewayError,
    RateLimitGatewayError,
)
from app.presentation.routes import router


logger = logging.getLogger(__name__)
app = FastAPI(title="Day 11 Assistant Memory Model")
app.include_router(router)


@app.exception_handler(InvalidUserMessage)
async def invalid_message_handler(request: Request, error: InvalidUserMessage):
    return JSONResponse(status_code=422, content={"detail": str(error)})


@app.exception_handler(ChatNotFound)
async def chat_not_found_handler(request: Request, error: ChatNotFound):
    return JSONResponse(status_code=404, content={"detail": "Чат не найден."})


@app.exception_handler(ChatPersistenceError)
async def chat_persistence_error_handler(request: Request, error: ChatPersistenceError):
    return JSONResponse(
        status_code=500,
        content={"detail": "Не удалось загрузить или сохранить память."},
    )


@app.exception_handler(ContextLimitExceeded)
async def context_limit_handler(request: Request, error: ContextLimitExceeded):
    detail = (
        f"Диалог превысил лимит контекста ({error.estimated_tokens} из "
        f"{error.context_limit} токенов). Сообщение не отправлено и не сохранено. "
        "Сократите рабочую или долговременную память либо начните новый чат."
    )
    return JSONResponse(
        status_code=413,
        content={
            "detail": detail,
            "estimated_tokens": error.estimated_tokens,
            "context_limit": error.context_limit,
        },
    )


@app.exception_handler(AuthenticationGatewayError)
async def authentication_error_handler(request: Request, error: AuthenticationGatewayError):
    return JSONResponse(
        status_code=502,
        content={"detail": "Провайдер отклонил API-ключ. Проверьте .env."},
    )


@app.exception_handler(RateLimitGatewayError)
async def rate_limit_error_handler(request: Request, error: RateLimitGatewayError):
    return JSONResponse(
        status_code=429,
        content={"detail": "Провайдер временно ограничил запросы. Повторите позже."},
    )


@app.exception_handler(GatewayTimeoutError)
async def timeout_error_handler(request: Request, error: GatewayTimeoutError):
    return JSONResponse(
        status_code=504,
        content={"detail": "Провайдер не ответил вовремя. Повторите запуск."},
    )


@app.exception_handler(LLMGatewayError)
async def gateway_error_handler(request: Request, error: LLMGatewayError):
    return JSONResponse(
        status_code=502,
        content={"detail": "Не удалось получить ответ от провайдера."},
    )


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, error: Exception):
    logger.exception("Unexpected request error", exc_info=error)
    return JSONResponse(
        status_code=500,
        content={"detail": "Внутренняя ошибка сервера."},
    )
```

- [ ] **Step 8: Обновить .env.example**

Replace `day11/backend/.env.example`:
```dotenv
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000

CHATS_DIR=data/chats
LONG_TERM_FILE=data/long_term.json
CANDIDATES_FILE=data/candidates.json

CONTEXT_LIMIT_TOKENS=8000
INPUT_PRICE_PER_MILLION=0.30
OUTPUT_PRICE_PER_MILLION=1.20

LONG_TERM_MAX_PER_CATEGORY=50
LONG_TERM_MAX_ITEM_CHARS=500
CANDIDATES_ENABLED=true
```

- [ ] **Step 9: Запустить тесты — должны пройти**

Run: `cd day11/backend && python -m pytest tests/test_memory_api.py -q`
Expected: PASS (5 passed).

- [ ] **Step 10: Прогнать весь backend-набор**

Run: `cd day11/backend && python -m pytest -q`
Expected: PASS (все тесты: models, memory, repository, agent, usage, token_counter, deepseek_gateway, memory_api).

- [ ] **Step 11: Commit**

```bash
git add day11/backend
git commit -m "feat(day11): memory API endpoints and settings"
```

---

### Task 7: Frontend — панель памяти и кандидаты

**Files:**
- Modify: `day11/frontend/src/api.js`
- Create: `day11/frontend/src/components/MemoryPanel.jsx`
- Create: `day11/frontend/src/components/CandidatesPanel.jsx`
- Modify: `day11/frontend/src/App.jsx`
- Modify: `day11/frontend/src/components/ChatPanel.jsx`
- Modify: `day11/frontend/src/styles.css`

**Interfaces:**
- Consumes: backend из Task 6.
- Produces: UI с панелью трёх слоёв, формой рабочей карточки, списком долговременной памяти, блоком кандидатов, чипом токенов по слоям.

- [ ] **Step 1: Обновить api.js**

Replace `day11/frontend/src/api.js`:
```javascript
async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(payload.detail || 'Ошибка запроса.');
    error.status = response.status;
    throw error;
  }
  return payload;
}

export function listChats() {
  return request('/api/chats');
}

export function createChat() {
  return request('/api/chats', { method: 'POST' });
}

export function getChat(chatId) {
  return request(`/api/chats/${chatId}`);
}

export function deleteChat(chatId) {
  return request(`/api/chats/${chatId}`, { method: 'DELETE' });
}

export function clearHistory(chatId) {
  return request(`/api/chats/${chatId}/messages`, { method: 'DELETE' });
}

export function sendMessage(chatId, message) {
  return request(`/api/chats/${chatId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ message }),
  });
}

export function saveWorkingMemory(chatId, working) {
  return request(`/api/chats/${chatId}/working-memory`, {
    method: 'PUT',
    body: JSON.stringify(working),
  });
}

export function completeWorkingMemory(chatId) {
  return request(`/api/chats/${chatId}/working-memory/complete`, {
    method: 'POST',
  });
}

export function resetWorkingMemory(chatId) {
  return request(`/api/chats/${chatId}/working-memory/reset`, {
    method: 'POST',
  });
}

export function getLongTerm() {
  return request('/api/long-term');
}

export function replaceLongTerm(longTerm) {
  return request('/api/long-term', {
    method: 'PUT',
    body: JSON.stringify(longTerm),
  });
}

export function deleteLongTermEntry(category, entryId) {
  return request(`/api/long-term/${category}/${entryId}`, { method: 'DELETE' });
}

export function listCandidates(status = 'pending') {
  return request(`/api/candidates?status=${status}`);
}

export function approveCandidate(candidateId) {
  return request(`/api/candidates/${candidateId}/approve`, { method: 'POST' });
}

export function rejectCandidate(candidateId) {
  return request(`/api/candidates/${candidateId}/reject`, { method: 'POST' });
}
```

- [ ] **Step 2: Создать MemoryPanel.jsx**

Create `day11/frontend/src/components/MemoryPanel.jsx`:
```jsx
import { useEffect, useState } from 'react';

const CATEGORY_LABELS = {
  profile: 'Профиль',
  decisions: 'Решения',
  knowledge: 'Знания',
};

export default function MemoryPanel({
  disabled,
  longTerm,
  messageCount,
  onAddEntry,
  onClearHistory,
  onCompleteWorking,
  onDeleteEntry,
  onResetWorking,
  onSaveWorking,
  working,
}) {
  const [goal, setGoal] = useState(working?.goal ?? '');
  const [constraints, setConstraints] = useState(
    (working?.constraints ?? []).join('\n')
  );
  const [decisions, setDecisions] = useState(
    (working?.decisions ?? []).join('\n')
  );
  const [newEntry, setNewEntry] = useState({ category: 'knowledge', text: '' });

  useEffect(() => {
    setGoal(working?.goal ?? '');
    setConstraints((working?.constraints ?? []).join('\n'));
    setDecisions((working?.decisions ?? []).join('\n'));
  }, [working]);

  function submitWorking(event) {
    event.preventDefault();
    onSaveWorking({
      goal,
      constraints: constraints.split('\n').map(item => item.trim()).filter(Boolean),
      decisions: decisions.split('\n').map(item => item.trim()).filter(Boolean),
      status: working?.status ?? 'active',
    });
  }

  return (
    <aside className="memory-panel" aria-label="Память ассистента">
      <div className="panel-kicker">MEMORY</div>
      <h2>Память ассистента</h2>

      <section className="memory-layer">
        <h3>Краткосрочная <span>{messageCount} сообщ.</span></h3>
        <button disabled={disabled} onClick={onClearHistory} type="button">
          Очистить историю
        </button>
      </section>

      <section className="memory-layer">
        <h3>Рабочая <span>{working?.status === 'done' ? 'завершена' : 'активна'}</span></h3>
        <form className="working-form" onSubmit={submitWorking}>
          <input
            disabled={disabled}
            onChange={event => setGoal(event.target.value)}
            placeholder="Цель задачи"
            value={goal}
          />
          <textarea
            disabled={disabled}
            onChange={event => setConstraints(event.target.value)}
            placeholder="Ограничения (по строке)"
            rows="2"
            value={constraints}
          />
          <textarea
            disabled={disabled}
            onChange={event => setDecisions(event.target.value)}
            placeholder="Решения (по строке)"
            rows="2"
            value={decisions}
          />
          <div className="working-actions">
            <button disabled={disabled} type="submit">Сохранить</button>
            <button disabled={disabled} onClick={onCompleteWorking} type="button">
              Завершить задачу
            </button>
            <button disabled={disabled} onClick={onResetWorking} type="button">
              Новая задача
            </button>
          </div>
        </form>
      </section>

      <section className="memory-layer">
        <h3>Долговременная <span>{longTerm ? longTerm.profile.length + longTerm.decisions.length + longTerm.knowledge.length : 0}</span></h3>
        {['profile', 'decisions', 'knowledge'].map(category => (
          <div className="longterm-category" key={category}>
            <strong>{CATEGORY_LABELS[category]}</strong>
            <ul>
              {(longTerm?.[category] ?? []).map(entry => (
                <li key={entry.id}>
                  <span>{entry.text}</span>
                  <button
                    aria-label={`Удалить ${entry.text}`}
                    disabled={disabled}
                    onClick={() => onDeleteEntry(category, entry.id)}
                    type="button"
                  >
                    🗑
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
        <div className="longterm-add">
          <select
            disabled={disabled}
            onChange={event =>
              setNewEntry(current => ({ ...current, category: event.target.value }))
            }
            value={newEntry.category}
          >
            {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
          <input
            disabled={disabled}
            onChange={event =>
              setNewEntry(current => ({ ...current, text: event.target.value }))
            }
            placeholder="Добавить в память"
            value={newEntry.text}
          />
          <button
            disabled={disabled || !newEntry.text.trim()}
            onClick={() => {
              onAddEntry(newEntry);
              setNewEntry(current => ({ ...current, text: '' }));
            }}
            type="button"
          >
            +
          </button>
        </div>
      </section>
    </aside>
  );
}
```

- [ ] **Step 3: Создать CandidatesPanel.jsx**

Create `day11/frontend/src/components/CandidatesPanel.jsx`:
```jsx
const CATEGORY_LABELS = {
  profile: 'Профиль',
  decisions: 'Решения',
  knowledge: 'Знания',
};

export default function CandidatesPanel({ candidates, disabled, onApprove, onReject }) {
  if (!candidates.length) return null;

  return (
    <section className="candidates-panel" aria-label="Кандидаты в память">
      <div className="panel-kicker">REMEMBER?</div>
      <h3>💾 Запомнить навсегда?</h3>
      <ul>
        {candidates.map(candidate => (
          <li key={candidate.id}>
            <span className="candidate-text">{candidate.text}</span>
            <span className="candidate-category">
              {CATEGORY_LABELS[candidate.category] ?? candidate.category}
            </span>
            <button
              disabled={disabled}
              onClick={() => onApprove(candidate.id)}
              type="button"
            >
              ✅
            </button>
            <button
              disabled={disabled}
              onClick={() => onReject(candidate.id)}
              type="button"
            >
              ✕
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
```

- [ ] **Step 4: Обновить ChatPanel.jsx**

В `day11/frontend/src/components/ChatPanel.jsx`:
- убрать импорты `FactsPanel`, `ModeSelector`, пропсы `facts/mode/onFactsChange/onModeChange/branches/activeBranchId/onFork/onSwitchBranch/onDeleteBranch`;
- заменить `ContextChip` на чип памяти:

```jsx
function MemoryChip({ memory }) {
  if (!memory) return null;
  return (
    <div className="context-chip">
      память: долг. {memory.long_term_tokens} · рабоч. {memory.working_tokens} · истор. {memory.history_tokens}
      {memory.candidate_tokens ? ` · кандидаты ${memory.candidate_tokens}` : ''}
    </div>
  );
}
```
- в списке сообщений для ассистента рендерить `<MemoryChip memory={item.memory} />` вместо `ContextChip`;
- удалить блок табов веток, кнопку fork, `ModeSelector`, `FactsPanel`, `MODE_LABELS`;
- placeholder композера: `'Напиши сообщение... (или «запомни: ...»)'`.

- [ ] **Step 5: Переписать App.jsx**

Replace `day11/frontend/src/App.jsx`:
```jsx
import { useEffect, useState } from 'react';
import {
  approveCandidate,
  clearHistory,
  completeWorkingMemory,
  createChat,
  deleteChat,
  deleteLongTermEntry,
  getChat,
  getLongTerm,
  listCandidates,
  listChats,
  rejectCandidate,
  replaceLongTerm,
  resetWorkingMemory,
  saveWorkingMemory,
  sendMessage,
} from './api.js';
import AgentFlow from './components/AgentFlow.jsx';
import CandidatesPanel from './components/CandidatesPanel.jsx';
import ChatPanel from './components/ChatPanel.jsx';
import ChatSidebar from './components/ChatSidebar.jsx';
import MemoryPanel from './components/MemoryPanel.jsx';

const initialStages = [
  { name: 'UI', status: 'completed' },
  { name: 'Agent', status: 'pending' },
  { name: 'DeepSeek API', status: 'pending' },
];

export default function App() {
  const [chats, setChats] = useState([]);
  const [selectedChatId, setSelectedChatId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [working, setWorking] = useState(null);
  const [longTerm, setLongTerm] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [message, setMessage] = useState('');
  const [result, setResult] = useState(null);
  const [stages, setStages] = useState(initialStages);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [initializing, setInitializing] = useState(true);
  const [dialogUsage, setDialogUsage] = useState(null);
  const [overflow, setOverflow] = useState('');

  function applyDetail(chat) {
    setMessages(chat.messages ?? []);
    setWorking(chat.working_memory ?? null);
    setDialogUsage(chat.dialog_usage ?? null);
  }

  async function refreshMemory() {
    setLongTerm(await getLongTerm());
    setCandidates(await listCandidates('pending'));
  }

  useEffect(() => {
    let cancelled = false;

    async function boot() {
      try {
        let availableChats = await listChats();
        if (!availableChats.length) {
          availableChats = [await createChat()];
        }
        if (cancelled) return;
        setChats(availableChats);
        await loadChat(availableChats[0].id);
        await refreshMemory();
      } catch (requestError) {
        if (!cancelled) setError(requestError.message);
      } finally {
        if (!cancelled) setInitializing(false);
      }
    }

    boot();
    return () => {
      cancelled = true;
    };
  }, []);

  async function loadChat(chatId) {
    const chat = await getChat(chatId);
    setSelectedChatId(chat.id);
    setResult(null);
    setError('');
    setOverflow('');
    setStages(initialStages);
    applyDetail(chat);
  }

  async function handleSelectChat(chatId) {
    if (loading || chatId === selectedChatId) return;
    setError('');
    try {
      await loadChat(chatId);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function handleCreateChat() {
    if (loading) return;
    try {
      const newChat = await createChat();
      setChats(current => [newChat, ...current]);
      setSelectedChatId(newChat.id);
      setMessages([]);
      setWorking(null);
      setResult(null);
      setDialogUsage(null);
      setOverflow('');
      setStages(initialStages);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function handleDeleteChat(chatId) {
    if (loading || !window.confirm('Удалить чат? Долговременная память сохранится.')) return;
    try {
      await deleteChat(chatId);
      const remaining = await listChats();
      if (remaining.length) {
        setChats(remaining);
        if (chatId === selectedChatId) await loadChat(remaining[0].id);
        return;
      }
      const newChat = await createChat();
      setChats([newChat]);
      await loadChat(newChat.id);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function sendToChat(text) {
    setLoading(true);
    setError('');
    setResult(null);
    setStages([
      { name: 'UI', status: 'completed' },
      { name: 'Agent', status: 'active' },
      { name: 'DeepSeek API', status: 'pending' },
    ]);
    setMessages(current => [...current, { role: 'user', content: text }]);

    try {
      const response = await sendMessage(selectedChatId, text);
      setMessages(current => [
        ...current,
        {
          role: 'assistant',
          content: response.answer,
          memory: response.usage?.memory ?? null,
        },
      ]);
      setResult(response);
      setStages(response.stages);
      setDialogUsage(response.usage);
      setChats(await listChats());
      applyDetail(await getChat(selectedChatId));
      await refreshMemory();
      return response;
    } catch (requestError) {
      setMessages(current => current.slice(0, -1));
      if (requestError.status === 413) {
        setOverflow(requestError.message);
      } else {
        setError(requestError.message);
      }
      return null;
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const trimmed = message.trim();
    if (!trimmed || !selectedChatId || loading || overflow) return;
    setMessage('');
    await sendToChat(trimmed);
  }

  async function handleSaveWorking(nextWorking) {
    try {
      applyDetail(await saveWorkingMemory(selectedChatId, nextWorking));
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function handleCompleteWorking() {
    try {
      applyDetail(await completeWorkingMemory(selectedChatId));
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function handleResetWorking() {
    try {
      applyDetail(await resetWorkingMemory(selectedChatId));
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function handleClearHistory() {
    if (!window.confirm('Очистить историю диалога? Рабочая и долговременная память останутся.')) return;
    try {
      applyDetail(await clearHistory(selectedChatId));
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function handleAddEntry({ category, text }) {
    try {
      const next = {
        profile: longTerm?.profile ?? [],
        decisions: longTerm?.decisions ?? [],
        knowledge: longTerm?.knowledge ?? [],
      };
      next[category] = [
        ...next[category],
        { id: crypto.randomUUID(), text, source_chat_id: selectedChatId, created_at: new Date().toISOString() },
      ];
      setLongTerm(await replaceLongTerm(next));
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function handleDeleteEntry(category, entryId) {
    try {
      await deleteLongTermEntry(category, entryId);
      await refreshMemory();
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function handleApprove(candidateId) {
    try {
      await approveCandidate(candidateId);
      await refreshMemory();
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function handleReject(candidateId) {
    try {
      await rejectCandidate(candidateId);
      await refreshMemory();
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  const disabled = loading || initializing;

  return (
    <main className="page-shell">
      <header className="hero">
        <div className="eyebrow"><span className="pulse-dot" /> DAY 11 / ASSISTANT MEMORY</div>
        <h1>Три слоя памяти.<br /><em>Один ассистент.</em></h1>
        <p className="hero-copy">
          Краткосрочная — история диалога. Рабочая — карточка текущей задачи.
          Долговременная — профиль, решения, знания навсегда. Вы решаете,
          что и куда сохраняется.
        </p>
      </header>

      <section className="workspace">
        <ChatSidebar
          chats={chats}
          disabled={disabled}
          onCreate={handleCreateChat}
          onDelete={handleDeleteChat}
          onSelect={handleSelectChat}
          selectedChatId={selectedChatId}
        />
        <ChatPanel
          error={error}
          loading={disabled}
          message={message}
          messages={messages}
          onChange={setMessage}
          onNewChat={handleCreateChat}
          onSubmit={handleSubmit}
          overflow={overflow}
          result={result}
        />
        <MemoryPanel
          disabled={disabled}
          longTerm={longTerm}
          messageCount={messages.length}
          onAddEntry={handleAddEntry}
          onClearHistory={handleClearHistory}
          onCompleteWorking={handleCompleteWorking}
          onDeleteEntry={handleDeleteEntry}
          onResetWorking={handleResetWorking}
          onSaveWorking={handleSaveWorking}
          working={working}
        />
      </section>

      <CandidatesPanel
        candidates={candidates}
        disabled={disabled}
        onApprove={handleApprove}
        onReject={handleReject}
      />

      <section className="flow-row">
        <AgentFlow loading={disabled} stages={stages} />
      </section>

      <footer className="page-footer">
        <span>FASTAPI + REACT</span>
        <span>THREE-LAYER MEMORY</span>
      </footer>
    </main>
  );
}
```

- [ ] **Step 6: Добавить стили**

Дописать в конец `day11/frontend/src/styles.css`:
```css
.memory-panel {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1rem;
  border: 1px solid var(--line, #2a2a35);
  border-radius: 12px;
  max-height: 720px;
  overflow-y: auto;
}
.memory-layer h3 {
  display: flex;
  justify-content: space-between;
  font-size: 0.9rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.memory-layer h3 span { opacity: 0.6; }
.working-form { display: flex; flex-direction: column; gap: 0.5rem; }
.working-form input, .working-form textarea, .longterm-add input, .longterm-add select {
  width: 100%;
  background: transparent;
  border: 1px solid var(--line, #2a2a35);
  border-radius: 8px;
  padding: 0.4rem 0.6rem;
  color: inherit;
}
.working-actions { display: flex; gap: 0.4rem; flex-wrap: wrap; }
.longterm-category ul { list-style: none; margin: 0.3rem 0; padding: 0; }
.longterm-category li { display: flex; justify-content: space-between; gap: 0.4rem; }
.longterm-add { display: grid; grid-template-columns: auto 1fr auto; gap: 0.4rem; margin-top: 0.5rem; }
.candidates-panel { margin-top: 1rem; padding: 1rem; border: 1px dashed var(--line, #2a2a35); border-radius: 12px; }
.candidates-panel ul { list-style: none; margin: 0; padding: 0; }
.candidates-panel li { display: flex; align-items: center; gap: 0.5rem; padding: 0.3rem 0; }
.candidate-category { opacity: 0.6; font-size: 0.8rem; }
.flow-row { margin-top: 1rem; }
```

- [ ] **Step 7: Собрать фронтенд**

Run: `cd day11/frontend && npm install && npm run build`
Expected: сборка без ошибок (`✓ built in ...`).

- [ ] **Step 8: Commit**

```bash
git add day11/frontend
git commit -m "feat(day11): memory panel, candidates confirmation UI"
```

---

### Task 8: README и ручной ритуал проверки

**Files:**
- Modify: `day11/README.md`
- Modify: `README.md` (корневой — добавить строку дня 11)

**Interfaces:**
- Consumes: всё выше.
- Produces: документация запуска, API, ручного ритуала, честных ограничений.

- [ ] **Step 1: Переписать day11/README.md**

Replace `day11/README.md`:
```markdown
# День 11: модель памяти ассистента

Самостоятельное продолжение `day10`. Три слоя памяти — краткосрочная, рабочая,
долговременная — хранятся раздельно, и вы явно решаете, что и куда сохраняется.

`day6`–`day10` не изменяются.

## Что изучаем

Дни 8–10 отвечали «что уместить в окно контекста прямо сейчас». День 11 отвечает
на другой вопрос: **что ассистент помнит вообще и кто это решает**.

| слой | что хранит | где лежит | время жизни |
| --- | --- | --- | --- |
| краткосрочная | история текущего диалога | `data/chats/<id>.json` | пока жив чат |
| рабочая | карточка задачи: цель, ограничения, решения, статус | `data/chats/<id>.json` | пока жива задача |
| долговременная | профиль, решения, знания | `data/long_term.json` | всегда, через все чаты |

Кандидаты на запоминание — `data/candidates.json`.

## Политика записи

- После ответа модель предлагает кандидатов («похоже на долговременное») —
  они попадают в блок «💾 Запомнить?». Вы подтверждаете ✅ или отклоняете ✕.
- Ручная команда `запомни: <текст>` пишет в долговременную **сразу**, минуя гейт.
- Рабочую карточку вы заполняете вручную — модель её не трогает.

## Как это влияет на ответы

Промпт собирается из трёх подписанных блоков: `## Долговременная память`,
`## Рабочая память`, `## История диалога`. Пустой слой не добавляется. Чип под
ответом показывает токены по слоям.

## Ручной ритуал

1. Чат А: «кстати, я аллергик — арахис нельзя» → блок «Запомнить?» → ✅ (Знания).
2. **Новый чат Б**: «что ты обо мне знаешь?» → отвечает из долговременной. Чат Б
   истории А не видел — это и есть доказательство разделения и глобальности.
3. Рабочая: заполните карточку, цель «бюджет 500» → сохраните → измените на
   «бюджет 900» → спросите «какой бюджет?» → 900 (перезапись, не append).
4. Удалите аллергию из долговременной (🗑) → новый чат В снова не знает.
5. Краткосрочная: «Очистить историю» → диалог забыт, долговременная помнится.
6. `запомни: я предпочитаю тёмную тему` → сразу в долговременной, без кандидата.

## Запуск

```bash
cd day11/backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
# .env: DEEPSEEK_API_KEY=... (см. .env.example)
uvicorn app.main:app --reload

cd ../frontend && npm install && npm run dev  # http://localhost:5173
```

Если `day10` держит порт 8000/5173 — сначала останови его.

## API

- `POST /api/chats/{id}/messages` `{message}` → `{answer, usage}`;
- `DELETE /api/chats/{id}/messages` — очистить краткосрочную историю;
- `GET|PUT /api/chats/{id}/working-memory` · `POST .../complete` · `POST .../reset`;
- `GET|PUT /api/long-term` · `DELETE /api/long-term/{category}/{entry_id}`;
- `GET /api/candidates?status=pending` · `POST /api/candidates/{id}/approve` ·
  `POST .../reject` · `DELETE /api/candidates?status=rejected`.

## Честные ограничения

- Поиск кандидатов — отдельный LLM-вызов на сообщение (токены, латентность).
- Если модель не заметила кандидата — факт не предложен; обход — команда
  `запомни:`.
- Долговременная инжектится **целиком** во все запросы: нет поиска по
  релевантности, растёт до капа `LONG_TERM_MAX_PER_CATEGORY`.
- Конфликт долговременной и краткосрочной не разрешается автоматически —
  побеждает то, что позже в промпте.
- Жизненный цикл рабочей памяти ручной (кнопка «Завершить задачу»).

## Тесты

```bash
cd day11/backend && .venv/bin/pytest -q
```

## Структура

- `app/application/memory.py` — сборка трёх блоков, парсеры кандидатов и команд;
- `app/application/agent.py` — `run(chat_id, text)`: команда → сборка → пре-чек →
  ответ → поиск кандидатов;
- `app/infrastructure/json_memory_repository.py` — три раздельных хранилища;
- `app/domain/models.py` — `WorkingMemory`, `LongTermMemory`, `MemoryCandidate`;
- `frontend/src/components/MemoryPanel.jsx`, `CandidatesPanel.jsx`.
```

- [ ] **Step 2: Добавить день 11 в корневой README**

Modify `README.md` — добавить после строки дня 10:
```markdown
- [`day11`](./day11) — модель памяти ассистента: краткосрочная, рабочая и долговременная память хранятся раздельно.
```

- [ ] **Step 3: Финальный прогон тестов**

Run: `cd day11/backend && python -m pytest -q`
Expected: PASS (все тесты).

- [ ] **Step 4: Commit**

```bash
git add day11/README.md README.md
git commit -m "docs(day11): memory model README and manual ritual"
```

---

## Self-Review (выполнено автором плана)

**Spec coverage:**
- §0 скаффолдинг → Task 1.
- §1 модель данных → Task 2.
- §2 раздельное хранилище → Task 4 (+ проверка файлов в тесте).
- §3 сборка промпта → Task 3.
- §4 поток запроса → Task 5.
- §5 политика записи (гибрид + команда + дубликаты 409) → Task 3/4/5/6.
- §6 API → Task 6.
- §7 UI → Task 7.
- §8 конфигурация → Task 6 (settings, .env.example).
- §9 ручной ритуал → Task 8.
- Тесты → Tasks 2–6.
- Границы → не реализуются, перечислены в README.

**Type consistency:** `WorkingMemory`, `LongTermMemory`, `LongTermEntry`,
`MemoryCandidate`, `MemoryInfo` используются одинаково в models/memory/repository/agent/routes.
`JsonMemoryRepository` создаётся с `chats_dir/long_term_path/candidates_path`
в Task 4, 6 и тестах. `Agent.run(chat_id, user_text)` без `mode` согласован в
Task 5 и routes Task 6.

**Placeholder scan:** плейсхолдеров нет; каждый шаг содержит команду и ожидаемый
результат либо полный код.
