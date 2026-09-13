# День 7: сохранение контекста Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Создать самостоятельный `day7` на основе `day6`, где несколько чатов сохраняются в JSON, восстанавливаются после перезапуска и передаются агенту как контекст.

**Architecture:** `day7` будет отдельной копией `day6`. `Agent` будет зависеть от `LLMGateway` и нового `ChatRepository`; `JsonChatRepository` будет читать и атомарно записывать `backend/data/chats.json`. FastAPI предоставит CRUD-операции для чатов и endpoint отправки сообщения, а React добавит список чатов и восстановление истории.

**Tech Stack:** Python 3.13, FastAPI, Pydantic Settings, pytest, OpenAI-compatible DeepSeek API, React, Vite, JSON file storage.

## Global Constraints

- `day6` не изменяется.
- Реализация находится в отдельной папке `day7`.
- История хранится в `day7/backend/data/chats.json`.
- `system prompt` не хранится; Agent добавляет его при каждом LLM-вызове.
- История сохраняется только после успешного ответа LLM.
- API endpoints: `POST /api/chats`, `GET /api/chats`, `GET /api/chats/{chat_id}`, `POST /api/chats/{chat_id}/messages`.
- API-ключ остаётся в backend и не попадает в frontend.
- Тесты не делают сетевых запросов в DeepSeek.
- JSON — единственный источник серверного контекста; `localStorage` не заменяет repository.

---

## File Map

### Created by copying `day6`

- `day7/README.md` — документация запуска, API и ручной проверки восстановления.
- `day7/backend/` — самостоятельный FastAPI-проект с собственным `.env`.
- `day7/frontend/` — самостоятельный React/Vite frontend.

### Backend files to modify or create

- `day7/backend/app/domain/models.py` — роли сообщений, модели чата и ошибки persistence.
- `day7/backend/app/application/ports/chat_repository.py` — контракт хранилища.
- `day7/backend/app/application/agent.py` — загрузка истории, вызов LLM и сохранение exchange.
- `day7/backend/app/infrastructure/json_chat_repository.py` — JSON persistence и atomic replace.
- `day7/backend/app/infrastructure/settings.py` — настройка `context_file`.
- `day7/backend/app/presentation/dependencies.py` — singleton repository и Agent dependency.
- `day7/backend/app/presentation/schemas.py` — chat API request/response schemas.
- `day7/backend/app/presentation/routes.py` — chat endpoints и message endpoint.
- `day7/backend/app/main.py` — title и handlers для chat/persistence errors.
- `day7/backend/tests/test_json_chat_repository.py` — repository tests.
- `day7/backend/tests/test_agent.py` — context forwarding and persistence tests.
- `day7/backend/tests/test_api.py` — chat endpoint tests.
- `day7/backend/.env.example` — DeepSeek and context file configuration.
- `day7/backend/.gitignore` — ignore `.env`, `data/chats.json`, caches.

### Frontend files to modify or create

- `day7/frontend/src/api.js` — chat list/create/load/send API functions.
- `day7/frontend/src/App.jsx` — selected chat, messages and lifecycle state.
- `day7/frontend/src/components/ChatSidebar.jsx` — chat list and new-chat action.
- `day7/frontend/src/components/ChatPanel.jsx` — full conversation rendering.
- `day7/frontend/src/styles.css` — sidebar, message history and responsive layout.

---

## Task 1: Create the Isolated Day 7 Baseline

**Files:**
- Create: `day7/` by copying tracked application files from `day6/`.
- Modify: `day7/backend/app/main.py:17` — change the FastAPI title to `Day 7 Context Persistence`.
- Modify: `day7/backend/.env.example` — add context file configuration.
- Modify: `day7/backend/.gitignore` — ignore persistence data.

**Interfaces:**
- Produces an independently runnable `day7/backend` and `day7/frontend`.
- Does not change any file under `day6/`.

- [ ] **Step 1: Copy the day6 application without secrets or generated files**

Run from repository root:

```bash
rsync -a \
  --exclude='.env' \
  --exclude='.venv' \
  --exclude='node_modules' \
  --exclude='__pycache__' \
  --exclude='.pytest_cache' \
  day6/ day7/
```

Expected: `day7/backend` and `day7/frontend` exist, but `day7/backend/.env` does not contain a copied secret.

- [ ] **Step 2: Verify the copy before editing**

```bash
git diff --exit-code -- day6
test -f day7/backend/app/application/agent.py
test -f day7/frontend/src/App.jsx
```

Expected: `git diff` exits successfully and both `test` commands succeed.

- [ ] **Step 3: Add the Day 7 configuration boundary**

Set `day7/backend/.env.example` to:

```env
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000
CONTEXT_FILE=data/chats.json
```

Append `data/chats.json` to `day7/backend/.gitignore` while keeping `.env`, `.venv`, `__pycache__`, and `.pytest_cache` ignored.

- [ ] **Step 4: Update the application title**

Change the copied FastAPI declaration to:

```python
app = FastAPI(title="Day 7 Context Persistence")
```

- [ ] **Step 5: Run the unchanged baseline tests**

```bash
cd day7/backend
pytest -q
```

Expected: the copied `day6` tests pass before the persistence changes.

- [ ] **Step 6: Commit the isolated baseline**

```bash
git add day7
git commit -m "feat: scaffold day7 context persistence"
```

---

## Task 2: Implement the JSON Chat Repository

**Files:**
- Create: `day7/backend/app/application/ports/chat_repository.py`.
- Modify: `day7/backend/app/domain/models.py:8-12` — allow `assistant` and add chat models/errors.
- Create: `day7/backend/app/infrastructure/json_chat_repository.py`.
- Create: `day7/backend/tests/test_json_chat_repository.py`.

**Interfaces:**
- Consumes: `Path` to a JSON file.
- Produces:
  - `ChatRepository.create_chat() -> Chat`.
  - `ChatRepository.list_chats() -> list[ChatSummary]`.
  - `ChatRepository.get_chat(chat_id: str) -> Chat`.
  - `ChatRepository.append_exchange(chat_id: str, user_content: str, assistant_content: str) -> Chat`.

- [ ] **Step 1: Write failing repository tests**

Create `day7/backend/tests/test_json_chat_repository.py`:

```python
import json

import pytest

from app.domain.models import ChatNotFound, ChatPersistenceError
from app.infrastructure.json_chat_repository import JsonChatRepository


@pytest.mark.asyncio
async def test_create_chat_persists_empty_chat(tmp_path):
    repository = JsonChatRepository(tmp_path / "chats.json")

    chat = await repository.create_chat()

    assert chat.title == "Новый чат"
    assert chat.messages == []
    assert json.loads((tmp_path / "chats.json").read_text()) == {
        "version": 1,
        "chats": [
            {
                "id": chat.id,
                "title": "Новый чат",
                "created_at": chat.created_at,
                "updated_at": chat.updated_at,
                "messages": [],
            }
        ],
    }


@pytest.mark.asyncio
async def test_exchange_survives_new_repository_instance(tmp_path):
    path = tmp_path / "chats.json"
    first = JsonChatRepository(path)
    chat = await first.create_chat()

    await first.append_exchange(chat.id, "Меня зовут Анна", "Приятно познакомиться")

    second = JsonChatRepository(path)
    restored = await second.get_chat(chat.id)

    assert [message.role for message in restored.messages] == ["user", "assistant"]
    assert [message.content for message in restored.messages] == [
        "Меня зовут Анна",
        "Приятно познакомиться",
    ]
    assert restored.title == "Меня зовут Анна"


@pytest.mark.asyncio
async def test_unknown_chat_raises_chat_not_found(tmp_path):
    repository = JsonChatRepository(tmp_path / "chats.json")

    with pytest.raises(ChatNotFound):
        await repository.get_chat("missing")


@pytest.mark.asyncio
async def test_malformed_json_raises_persistence_error(tmp_path):
    path = tmp_path / "chats.json"
    path.write_text("not-json")
    repository = JsonChatRepository(path)

    with pytest.raises(ChatPersistenceError):
        await repository.list_chats()
```

- [ ] **Step 2: Run the focused tests to verify failure**

```bash
cd day7/backend
pytest tests/test_json_chat_repository.py -q
```

Expected: FAIL because the repository contract and implementation do not exist yet.

- [ ] **Step 3: Define the domain models and repository protocol**

Extend `ChatMessage` and add these models:

```python
@dataclass(frozen=True)
class ChatMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class ChatSummary:
    id: str
    title: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class Chat:
    id: str
    title: str
    created_at: str
    updated_at: str
    messages: list[ChatMessage]


class ChatNotFound(RuntimeError):
    pass


class ChatPersistenceError(RuntimeError):
    pass
```

Create `chat_repository.py`:

```python
from typing import Protocol

from app.domain.models import Chat, ChatSummary


class ChatRepository(Protocol):
    async def create_chat(self) -> Chat: ...
    async def list_chats(self) -> list[ChatSummary]: ...
    async def get_chat(self, chat_id: str) -> Chat: ...
    async def append_exchange(
        self,
        chat_id: str,
        user_content: str,
        assistant_content: str,
    ) -> Chat: ...
```

- [ ] **Step 4: Implement JSON persistence with atomic writes**

Implement `JsonChatRepository` with these rules:

```python
class JsonChatRepository:
    def __init__(self, path: Path):
        self._path = path
        self._lock = asyncio.Lock()
```

The implementation must:

- create the parent directory and an empty `{"version": 1, "chats": []}` file when missing;
- use `uuid.uuid4()` for chat ids;
- use `datetime.now(timezone.utc).isoformat()` for timestamps;
- store only `user` and `assistant` messages;
- replace `Новый чат` with the first user message on the first exchange;
- replace the destination file with `os.replace(temp_path, self._path)` after a complete JSON write;
- raise `ChatNotFound` for an unknown id;
- raise `ChatPersistenceError` for malformed JSON or invalid storage shape;
- protect read-modify-write operations with the repository lock.

Use this title helper:

```python
def _chat_title(content: str) -> str:
    compact = " ".join(content.split())
    return compact[:50] or "Новый чат"
```

- [ ] **Step 5: Run repository tests to verify success**

```bash
cd day7/backend
pytest tests/test_json_chat_repository.py -q
```

Expected: all repository tests pass.

- [ ] **Step 6: Commit the repository slice**

```bash
git add day7/backend/app/domain/models.py \
  day7/backend/app/application/ports/chat_repository.py \
  day7/backend/app/infrastructure/json_chat_repository.py \
  day7/backend/tests/test_json_chat_repository.py
git commit -m "feat: persist day7 chats in json"
```

---

## Task 3: Make Agent Use Conversation History

**Files:**
- Modify: `day7/backend/app/application/agent.py:15-47`.
- Modify: `day7/backend/tests/test_agent.py`.

**Interfaces:**
- Consumes: `ChatRepository.get_chat()` and `ChatRepository.append_exchange()` from Task 2.
- Produces: `Agent.run(chat_id: str, user_text: str) -> AgentResult`.

- [ ] **Step 1: Add a fake repository and failing context test**

Add to `test_agent.py`:

```python
from app.domain.models import Chat, ChatMessage


class FakeRepository:
    def __init__(self):
        self.chat = Chat(
            id="chat-1",
            title="Новый чат",
            created_at="2026-09-13T12:00:00+00:00",
            updated_at="2026-09-13T12:00:00+00:00",
            messages=[
                ChatMessage(role="user", content="Меня зовут Анна"),
                ChatMessage(role="assistant", content="Приятно познакомиться"),
            ],
        )
        self.saved = None

    async def get_chat(self, chat_id):
        assert chat_id == self.chat.id
        return self.chat

    async def append_exchange(self, chat_id, user_content, assistant_content):
        self.saved = (chat_id, user_content, assistant_content)
        return self.chat


@pytest.mark.asyncio
async def test_agent_sends_previous_history_and_saves_exchange():
    gateway = FakeGateway()
    repository = FakeRepository()

    result = await Agent(gateway, repository).run("chat-1", "Как меня зовут?")

    assert [message.role for message in gateway.messages] == [
        "system",
        "user",
        "assistant",
        "user",
    ]
    assert gateway.messages[-2].content == "Приятно познакомиться"
    assert gateway.messages[-1].content == "Как меня зовут?"
    assert repository.saved == ("chat-1", "Как меня зовут?", result.answer)
```

Update `FakeGateway` to return a stable `LLMResponse("Анна", "deepseek-chat")` for this test.

- [ ] **Step 2: Run the focused test to verify failure**

```bash
cd day7/backend
pytest tests/test_agent.py::test_agent_sends_previous_history_and_saves_exchange -q
```

Expected: FAIL because `Agent` still accepts only a gateway and has the old `run(user_text)` signature.

- [ ] **Step 3: Update Agent to compose history**

Change the constructor and method to this shape:

```python
class Agent:
    def __init__(
        self,
        gateway: LLMGateway,
        repository: ChatRepository,
        model: str = "deepseek-chat",
    ):
        self._gateway = gateway
        self._repository = repository
        self._model = model

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
        messages = [ChatMessage(role="system", content=SYSTEM_PROMPT)]
        messages.extend(chat.messages)
        messages.append(ChatMessage(role="user", content=message))

        started_at = perf_counter()
        response = await self._gateway.complete(messages)
        answer = response.text.strip()
        await self._repository.append_exchange(chat_id, message, answer)

        return AgentResult(
            answer=answer,
            model=response.model or self._model,
            duration_ms=round((perf_counter() - started_at) * 1000),
            stages=[
                AgentStage(name="UI", status="completed"),
                AgentStage(name="Agent", status="completed"),
                AgentStage(name="DeepSeek API", status="completed"),
            ],
        )
```

Keep the existing validation rules and error behavior. Do not persist the user message before the gateway succeeds.

- [ ] **Step 4: Update existing Agent tests and run them**

Every existing successful call changes from:

```python
await Agent(gateway).run("hello")
```

to:

```python
await Agent(gateway, FakeRepository()).run("chat-1", "hello")
```

Run:

```bash
cd day7/backend
pytest tests/test_agent.py -q
```

Expected: all Agent tests pass, including the new context test.

- [ ] **Step 5: Commit the Agent slice**

```bash
git add day7/backend/app/application/agent.py day7/backend/tests/test_agent.py
git commit -m "feat: pass persisted history through agent"
```

---

## Task 4: Expose Chat Persistence Through FastAPI

**Files:**
- Modify: `day7/backend/app/infrastructure/settings.py:4-11`.
- Modify: `day7/backend/app/presentation/dependencies.py:8-20`.
- Modify: `day7/backend/app/presentation/schemas.py`.
- Modify: `day7/backend/app/presentation/routes.py`.
- Modify: `day7/backend/app/main.py`.
- Modify: `day7/backend/tests/test_api.py`.

**Interfaces:**
- Consumes: `Agent`, `ChatRepository`, `ChatNotFound`, and `ChatPersistenceError`.
- Produces the four documented HTTP endpoints and JSON response shapes.

- [ ] **Step 1: Add failing API tests for chat lifecycle**

Add API tests using a fake repository and fake Agent dependency:

```python
class FakeRepository:
    def __init__(self):
        self.error = None
        self.chat = Chat(
            id="chat-1",
            title="Новый чат",
            created_at="2026-09-13T12:00:00+00:00",
            updated_at="2026-09-13T12:00:00+00:00",
            messages=[
                ChatMessage(role="user", content="Меня зовут Анна"),
                ChatMessage(role="assistant", content="Приятно познакомиться"),
            ],
        )

    async def create_chat(self):
        return self.chat

    async def list_chats(self):
        return [ChatSummary(
            id=self.chat.id,
            title=self.chat.title,
            created_at=self.chat.created_at,
            updated_at=self.chat.updated_at,
        )]

    async def get_chat(self, chat_id):
        if self.error:
            raise self.error
        if chat_id != self.chat.id:
            raise ChatNotFound(chat_id)
        return self.chat


class FakeAgent:
    def __init__(self):
        self.calls = []

    async def run(self, chat_id, message):
        self.calls.append((chat_id, message))
        return AgentResult(
            answer="Анна",
            model="deepseek-chat",
            duration_ms=3,
            stages=[
                AgentStage(name="UI", status="completed"),
                AgentStage(name="Agent", status="completed"),
                AgentStage(name="DeepSeek API", status="completed"),
            ],
        )


@pytest.fixture
def client():
    fake_repository = FakeRepository()
    fake_agent = FakeAgent()
    app.dependency_overrides[get_repository] = lambda: fake_repository
    app.dependency_overrides[get_agent] = lambda: fake_agent
    with TestClient(app) as test_client:
        yield test_client, fake_repository, fake_agent
    app.dependency_overrides.clear()


def test_create_chat_returns_summary(client):
    response = client[0].post("/api/chats")

    assert response.status_code == 201
    assert response.json()["title"] == "Новый чат"
    assert response.json()["id"] == "chat-1"


def test_get_chat_returns_history(client):
    response = client[0].get("/api/chats/chat-1")

    assert response.status_code == 200
    assert response.json()["messages"] == [
        {"role": "user", "content": "Меня зовут Анна"},
        {"role": "assistant", "content": "Приятно познакомиться"},
    ]


def test_list_chats_returns_summaries(client):
    response = client[0].get("/api/chats")

    assert response.status_code == 200
    assert response.json()[0]["id"] == "chat-1"
    assert "messages" not in response.json()[0]


def test_send_message_passes_chat_id_to_agent(client):
    response = client[0].post(
        "/api/chats/chat-1/messages",
        json={"message": "Как меня зовут?"},
    )

    assert response.status_code == 200
    assert response.json()["chat_id"] == "chat-1"
    assert client[2].calls == [("chat-1", "Как меня зовут?")]


def test_unknown_chat_returns_404(client):
    client[1].error = ChatNotFound("missing")

    response = client[0].get("/api/chats/missing")

    assert response.status_code == 404
```

The fixture imports `Chat`, `ChatMessage`, `ChatSummary`, `ChatNotFound`, `AgentResult`, `AgentStage`, `app`, `get_repository`, and `get_agent`, and clears `app.dependency_overrides` after each test.

- [ ] **Step 2: Run API tests to verify failure**

```bash
cd day7/backend
pytest tests/test_api.py -q
```

Expected: FAIL because the chat routes and schemas do not exist.

- [ ] **Step 3: Add context file configuration and dependencies**

Add to `Settings`:

```python
context_file: str = "data/chats.json"
```

Add cached repository construction:

```python
from pathlib import Path

from app.application.ports.chat_repository import ChatRepository
from app.infrastructure.json_chat_repository import JsonChatRepository


@lru_cache
def get_repository() -> JsonChatRepository:
    settings = get_settings()
    return JsonChatRepository(Path(settings.context_file))
```

Update `get_agent()` to construct:

```python
return Agent(
    gateway,
    repository=get_repository(),
    model=settings.deepseek_model,
)
```

- [ ] **Step 4: Add Pydantic schemas**

Add these schemas:

```python
class ChatMessageResponse(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatSummaryResponse(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str


class ChatDetailResponse(ChatSummaryResponse):
    messages: list[ChatMessageResponse]


class ChatMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)

    @field_validator("message")
    @classmethod
    def message_cannot_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message cannot be blank")
        return value


class ChatResponse(BaseModel):
    chat_id: str
    answer: str
    model: str
    duration_ms: int
    stages: list[StageResponse]
```

- [ ] **Step 5: Add repository and Agent routes**

Implement these route signatures:

```python
@router.post("/api/chats", response_model=ChatSummaryResponse, status_code=201)
async def create_chat(
    repository: Annotated[ChatRepository, Depends(get_repository)],
): ...


@router.get("/api/chats", response_model=list[ChatSummaryResponse])
async def list_chats(
    repository: Annotated[ChatRepository, Depends(get_repository)],
): ...


@router.get("/api/chats/{chat_id}", response_model=ChatDetailResponse)
async def get_chat(
    chat_id: str,
    repository: Annotated[ChatRepository, Depends(get_repository)],
): ...


@router.post("/api/chats/{chat_id}/messages", response_model=ChatResponse)
async def send_message(
    chat_id: str,
    request: ChatMessageRequest,
    agent: Annotated[Agent, Depends(get_agent)],
): ...
```

The message route calls exactly:

```python
result = await agent.run(chat_id, request.message)
```

It must not call `DeepSeekGateway` directly. Add exception handlers in `main.py` mapping `ChatNotFound` to `404` and `ChatPersistenceError` to a safe `500` response.

- [ ] **Step 6: Run all backend tests**

```bash
cd day7/backend
pytest -q
```

Expected: repository, Agent, and API tests pass without a network request.

- [ ] **Step 7: Commit the FastAPI slice**

```bash
git add day7/backend/app day7/backend/tests/test_api.py day7/backend/.env.example
git commit -m "feat: expose persistent chat api"
```

---

## Task 5: Add Multiple Chats to the React Interface

**Files:**
- Modify: `day7/frontend/src/api.js`.
- Modify: `day7/frontend/src/App.jsx`.
- Create: `day7/frontend/src/components/ChatSidebar.jsx`.
- Modify: `day7/frontend/src/components/ChatPanel.jsx`.
- Modify: `day7/frontend/src/styles.css`.

**Interfaces:**
- Consumes:
  - `GET /api/chats` returning `ChatSummaryResponse[]`;
  - `POST /api/chats` returning `ChatSummaryResponse`;
  - `GET /api/chats/{chat_id}` returning `ChatDetailResponse`;
  - `POST /api/chats/{chat_id}/messages` returning `ChatResponse`.
- Produces a selected-chat UI that reloads history from backend after a browser/backend restart.

- [ ] **Step 1: Add the API client functions**

Extend `api.js` with:

```javascript
async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || 'Ошибка запроса.');
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

export function sendMessage(chatId, message) {
  return request(`/api/chats/${chatId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ message }),
  });
}
```

- [ ] **Step 2: Add the chat sidebar component**

Create `ChatSidebar.jsx` with props `{ chats, selectedChatId, onSelect, onCreate, disabled }`. Render a button labelled `Новый чат` and one button per chat. The selected chat receives `aria-current="true"`; the button text is `chat.title`.

- [ ] **Step 3: Replace single-response state with selected-chat state**

In `App.jsx`, maintain:

```javascript
const [chats, setChats] = useState([]);
const [selectedChatId, setSelectedChatId] = useState(null);
const [messages, setMessages] = useState([]);
const [result, setResult] = useState(null);
const [error, setError] = useState('');
const [loading, setLoading] = useState(false);
```

On mount, call `listChats()`. If the list is empty, call `createChat()`; otherwise select the first chat and call `getChat(id)`. `handleSelectChat(id)` calls `getChat(id)` and replaces `messages`. `handleCreateChat()` calls `createChat()`, prepends the result to `chats`, selects it, and clears `messages`.

- [ ] **Step 4: Send messages for the selected chat**

The submit handler must reject when there is no selected chat or another request is loading. On success:

```javascript
const response = await sendMessage(selectedChatId, trimmedMessage);
setMessages(current => [
  ...current,
  { role: 'user', content: trimmedMessage },
  { role: 'assistant', content: response.answer },
]);
setResult(response);
setChats(await listChats());
```

On failure, restore the previous messages array and show the existing safe error card. Keep AgentFlow status handling from `day6`.

- [ ] **Step 5: Render the entire conversation**

Change `ChatPanel` to receive `messages` instead of separate `answer` and `message` display state. Render each item with the existing visual message classes:

```jsx
{messages.map((item, index) => (
  <div
    className={`message ${item.role === 'user' ? 'user-message' : 'agent-message'}`}
    key={`${item.role}-${index}`}
  >
    {item.content}
  </div>
))}
```

Keep the composer controlled by the draft `message` state and keep Enter/Shift+Enter behavior.

- [ ] **Step 6: Add responsive sidebar styles and update copy**

Add a two-column shell with a narrow sidebar on desktop and a stacked layout below `760px`. Preserve the existing dark visual language. Update:

```text
DAY 06 / FIRST AGENT → DAY 07 / CONTEXT PERSISTENCE
ONE REQUEST / NO MEMORY → PERSISTENT JSON CONTEXT
```

The sidebar must remain usable on mobile and the message list must scroll without hiding the composer.

- [ ] **Step 7: Build the frontend**

```bash
cd day7/frontend
npm run build
```

Expected: Vite production build completes successfully.

- [ ] **Step 8: Commit the frontend slice**

```bash
git add day7/frontend
git commit -m "feat: add persistent chat list to frontend"
```

---

## Task 6: Document and Verify Restart Persistence

**Files:**
- Modify: `day7/README.md`.

**Interfaces:**
- Consumes the completed backend and frontend from Tasks 1-5.
- Produces reproducible setup instructions and evidence for the assignment.

- [ ] **Step 1: Document the Day 7 behavior**

Update the README to explain:

- the difference from `day6`;
- JSON format and `CONTEXT_FILE`;
- the four chat endpoints;
- that `system prompt` is generated and not persisted;
- that only successful exchanges are written;
- backend and frontend startup commands;
- the manual restart scenario using `Меня зовут Анна` and `Как меня зовут?`;
- that `.env` and `data/chats.json` are not committed.

- [ ] **Step 2: Run the complete automated verification**

```bash
cd day7/backend
pytest -q
cd ../frontend
npm run build
cd ../..
git diff --check
```

Expected: all backend tests pass, frontend build succeeds, and `git diff --check` produces no output.

- [ ] **Step 3: Run the real restart scenario**

Start backend from `day7/backend` and frontend from `day7/frontend`. Then:

1. Create a new chat in the UI.
2. Send `Меня зовут Анна`.
3. Confirm the JSON file contains the user and assistant messages.
4. Stop the backend process.
5. Start the backend again with the same `CONTEXT_FILE`.
6. Reload the frontend.
7. Select the existing chat.
8. Send `Как меня зовут?`.
9. Confirm the answer uses `Анна`.

- [ ] **Step 4: Verify isolation and secret safety**

```bash
git diff --exit-code -- day6
git status --short
git check-ignore -v day7/backend/.env day7/backend/data/chats.json
```

Expected: `day6` has no diff, runtime secrets/data are ignored, and only intended `day7` source/docs are tracked.

- [ ] **Step 5: Commit documentation and final verification**

```bash
git add day7/README.md
git commit -m "docs: document day7 context recovery"
```

---

## Final Acceptance Checklist

- [ ] `day6` remains unchanged.
- [ ] `day7` runs independently with its own backend and frontend.
- [ ] Multiple chats can be created and selected.
- [ ] Chat history is stored in JSON on the backend.
- [ ] Agent sends previous `user` and `assistant` messages to the LLM.
- [ ] A new repository instance restores data from disk.
- [ ] Failed LLM requests do not append incomplete history.
- [ ] Unknown chat ids return `404`.
- [ ] Backend tests pass without a network request.
- [ ] Frontend production build passes.
- [ ] Manual stop/start scenario proves context recovery.
