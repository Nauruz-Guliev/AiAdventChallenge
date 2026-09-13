# День 6: Первый LLM-агент Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Создать учебный `day6` с отдельным Python-классом `Agent`, который принимает одно сообщение, вызывает DeepSeek через gateway и показывает результат в React web-интерфейсе.

**Architecture:** FastAPI будет тонким HTTP-адаптером. Use case `Agent` будет зависеть только от протокола `LLMGateway`, а `DeepSeekGateway` реализует этот протокол через OpenAI-compatible Python SDK. React/Vite будет отдельным frontend, который вызывает `/api/chat` и визуализирует чат вместе со схемой `UI → Agent → DeepSeek API → UI`.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, pydantic-settings, OpenAI Python SDK, pytest, pytest-asyncio, React, Vite, vanilla CSS, native `fetch`.

## Global Constraints

- Новый проект располагается в `day6` и не изменяет реализацию предыдущих дней.
- Backend и вся предметная логика реализуются на Python.
- Web-интерфейс реализуется на React/Vite.
- Используется DeepSeek API через OpenAI-compatible Python SDK.
- Каждый запрос независим; история диалога не хранится.
- Используется модель `deepseek-chat`; её можно переопределить переменной `DEEPSEEK_MODEL`.
- DeepSeek API вызывается через `https://api.deepseek.com/v1`, если `DEEPSEEK_BASE_URL` не задан явно.
- API-ключ хранится только в `day6/backend/.env` и никогда не передаётся frontend.
- Streaming, авторизация пользователей, база данных и долговременная память агента не входят в первый этап.
- Unit- и API-тесты не используют реальный DeepSeek API.

---

## File Map

### Backend

- Create `day6/backend/pyproject.toml`: pytest configuration and package metadata.
- Create `day6/backend/requirements.txt`: runtime and test dependencies.
- Create `day6/backend/.env.example`: safe DeepSeek configuration template.
- Create `day6/backend/.gitignore`: ignore Python virtualenv and caches.
- Create `day6/backend/app/domain/models.py`: immutable domain data models and domain errors.
- Create `day6/backend/app/application/ports/llm_gateway.py`: gateway protocol.
- Create `day6/backend/app/application/agent.py`: `Agent` use case.
- Create `day6/backend/app/infrastructure/settings.py`: environment settings.
- Create `day6/backend/app/infrastructure/deepseek_gateway.py`: DeepSeek adapter and provider error mapping.
- Create `day6/backend/app/presentation/schemas.py`: request and response Pydantic models.
- Create `day6/backend/app/presentation/dependencies.py`: dependency injection for the configured agent.
- Create `day6/backend/app/presentation/routes.py`: `/api/chat` HTTP route.
- Create `day6/backend/app/main.py`: FastAPI application and error handlers.
- Create `day6/backend/tests/test_agent.py`: isolated Agent unit tests.
- Create `day6/backend/tests/test_api.py`: FastAPI tests with dependency overrides.
- Create `day6/backend/tests/test_deepseek_gateway.py`: adapter tests with a fake SDK client.

### Frontend

- Create `day6/frontend/package.json`: React/Vite scripts and dependencies.
- Create `day6/frontend/.gitignore`: ignore frontend dependencies and build output.
- Create `day6/frontend/index.html`: browser entry point.
- Create `day6/frontend/src/main.jsx`: React bootstrap.
- Create `day6/frontend/src/App.jsx`: request state and page composition.
- Create `day6/frontend/src/api.js`: typed-by-convention HTTP client function.
- Create `day6/frontend/src/components/ChatPanel.jsx`: message form and answer display.
- Create `day6/frontend/src/components/AgentFlow.jsx`: request stage visualization.
- Create `day6/frontend/src/styles.css`: responsive visual system.
- Create `day6/frontend/vite.config.js`: development proxy from Vite to FastAPI.

### Documentation

- Create `day6/README.md`: learning-oriented setup, architecture explanation, and test commands.
- Modify root `README.md`: add the `day6` entry.

---

## Task 1: Scaffold Python and React Projects

**Files:**
- Create: `day6/backend/pyproject.toml`
- Create: `day6/backend/requirements.txt`
- Create: `day6/backend/.env.example`
- Create: `day6/backend/.gitignore`
- Create: `day6/backend/app/__init__.py`
- Create: `day6/backend/app/domain/__init__.py`
- Create: `day6/backend/app/application/__init__.py`
- Create: `day6/backend/app/application/ports/__init__.py`
- Create: `day6/backend/app/infrastructure/__init__.py`
- Create: `day6/backend/app/presentation/__init__.py`
- Create: `day6/backend/tests/__init__.py`
- Create: `day6/frontend/package.json`
- Create: `day6/frontend/.gitignore`
- Create: `day6/frontend/index.html`
- Create: `day6/frontend/src/main.jsx`
- Create: `day6/frontend/src/App.jsx`
- Create: `day6/frontend/vite.config.js`

**Interfaces:**
- Produces a runnable Python test environment and a runnable Vite shell.
- Backend test command is `pytest` from `day6/backend`.
- Frontend commands are `npm run dev` and `npm run build` from `day6/frontend`.

- [ ] **Step 1: Write the Python project configuration**

Create `pyproject.toml` with Python 3.11 compatibility and pytest discovery:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "advent-challenge-day6-backend"
version = "0.1.0"
requires-python = ">=3.11"

[tool.pytest.ini_options]
pythonpath = ["."]
asyncio_mode = "auto"
```

Create `requirements.txt`:

```text
fastapi>=0.115,<1
uvicorn[standard]>=0.30,<1
pydantic>=2.9,<3
pydantic-settings>=2.6,<3
openai>=1.60,<2
pytest>=8.3,<9
pytest-asyncio>=0.24,<1
httpx>=0.27,<1
```

- [ ] **Step 2: Add safe environment defaults**

Create `backend/.env.example`:

```env
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000
```

Do not create or commit a real `.env` file.

Create `backend/.gitignore`:

```text
.venv/
__pycache__/
.pytest_cache/
```

- [ ] **Step 3: Create the minimal React/Vite shell**

Use these scripts and dependencies in `frontend/package.json`:

```json
{
  "name": "advent-challenge-day6-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {"dev": "vite", "build": "vite build"},
  "dependencies": {"@vitejs/plugin-react": "latest", "vite": "latest", "react": "latest", "react-dom": "latest"},
  "devDependencies": {}
}
```

Create `frontend/.gitignore`:

```text
node_modules/
dist/
```

`src/main.jsx` should render `<App />` into `#root`; `src/App.jsx` can initially render a heading so the Vite shell has a visible entry point.

Configure `vite.config.js` with a development proxy:

```js
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': 'http://127.0.0.1:8000' } },
});
```

- [ ] **Step 4: Install and verify the scaffold**

Run:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -c "import fastapi, openai, pydantic_settings"
cd ../frontend
npm install
npm run build
```

Expected: the Python import command succeeds, and Vite finishes with a successful production build.

- [ ] **Step 5: Commit the scaffold**

```bash
git add day6
git commit -m "feat: scaffold day6 Python agent app"
```

## Task 2: Define Domain Models and the LLM Gateway Contract

**Files:**
- Create: `day6/backend/app/domain/models.py`
- Create: `day6/backend/app/application/ports/llm_gateway.py`
- Create: `day6/backend/tests/test_agent.py`

**Interfaces:**
- Produces `ChatMessage`, `LLMResponse`, `AgentStage`, `AgentResult`.
- Produces `LLMGateway.complete(messages: list[ChatMessage]) -> LLMResponse` as an async protocol.

- [ ] **Step 1: Write model contract tests**

Add tests that verify immutable model construction and the fields needed later:

```python
from app.domain.models import AgentResult, AgentStage, LLMResponse


def test_result_contains_answer_model_duration_and_stages():
    result = AgentResult(
        answer="test answer",
        model="deepseek-chat",
        duration_ms=12,
        stages=[AgentStage(name="Agent", status="completed")],
    )

    assert result.answer == "test answer"
    assert result.model == "deepseek-chat"
    assert result.stages[0].status == "completed"


def test_llm_response_contains_text_and_model():
    response = LLMResponse(text="hello", model="deepseek-chat")
    assert response.text == "hello"
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
cd day6/backend
pytest tests/test_agent.py -q
```

Expected: FAIL because the domain models do not exist yet.

- [ ] **Step 3: Implement the domain models and protocol**

Use frozen dataclasses and typed literals:

```python
# app/domain/models.py
from dataclasses import dataclass
from typing import Literal

StageStatus = Literal["pending", "active", "completed", "error"]


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["system", "user"]
    content: str


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str


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


class InvalidUserMessage(ValueError):
    pass


class LLMGatewayError(RuntimeError):
    pass


class AuthenticationGatewayError(LLMGatewayError):
    pass


class RateLimitGatewayError(LLMGatewayError):
    pass


class GatewayTimeoutError(LLMGatewayError):
    pass
```

```python
# app/application/ports/llm_gateway.py
from typing import Protocol
from app.domain.models import ChatMessage, LLMResponse


class LLMGateway(Protocol):
    async def complete(self, messages: list[ChatMessage]) -> LLMResponse:
        ...
```

- [ ] **Step 4: Run the tests and verify they pass**

Run `pytest tests/test_agent.py -q`.

Expected: PASS for the model contract tests.

- [ ] **Step 5: Commit the contracts**

```bash
git add day6/backend/app/domain day6/backend/app/application/ports day6/backend/tests/test_agent.py
git commit -m "feat: define day6 agent domain contracts"
```

## Task 3: Implement the Agent Use Case with a Fake Gateway

**Files:**
- Modify: `day6/backend/app/application/agent.py`
- Modify: `day6/backend/tests/test_agent.py`

**Interfaces:**
- Consumes: `LLMGateway.complete(...)` from Task 2.
- Produces: `Agent(gateway, model="deepseek-chat").run(user_text) -> AgentResult`.

- [ ] **Step 1: Write failing Agent tests**

Add an async fake and tests for success, validation, and provider failure:

```python
import pytest
from app.application.agent import Agent
from app.domain.models import LLMGatewayError, LLMResponse, InvalidUserMessage


class FakeGateway:
    def __init__(self, response=None, error=None):
        self.response = response or LLMResponse("fake answer", "deepseek-chat")
        self.error = error
        self.messages = None

    async def complete(self, messages):
        self.messages = messages
        if self.error:
            raise self.error
        return self.response


@pytest.mark.asyncio
async def test_agent_sends_user_message_and_returns_answer():
    gateway = FakeGateway()
    result = await Agent(gateway).run("  hello  ")

    assert result.answer == "fake answer"
    assert gateway.messages[-1].role == "user"
    assert gateway.messages[-1].content == "hello"
    assert [stage.status for stage in result.stages] == ["completed"] * 3


@pytest.mark.asyncio
async def test_agent_rejects_blank_message():
    with pytest.raises(InvalidUserMessage):
        await Agent(FakeGateway()).run("   ")


@pytest.mark.asyncio
async def test_agent_preserves_gateway_error():
    with pytest.raises(LLMGatewayError):
        await Agent(FakeGateway(error=LLMGatewayError("provider failed"))).run("hello")
```

- [ ] **Step 2: Run the tests to verify failure**

Run `pytest tests/test_agent.py -q`.

Expected: FAIL because `Agent` is not implemented.

- [ ] **Step 3: Implement the Agent**

Implement these rules:

- trim the message;
- reject blank input and input over 4000 characters with `InvalidUserMessage`;
- send a system message that requests a concise answer in the user’s language and forbids hidden chain-of-thought disclosure;
- send exactly one user message;
- measure elapsed milliseconds with `time.perf_counter()`;
- return three completed stages for a successful call: `UI`, `Agent`, `DeepSeek API`;
- do not store the message or response after `run` returns.

The constructor should accept any object satisfying `LLMGateway`, not a concrete DeepSeek class.

- [ ] **Step 4: Run the isolated Agent tests**

Run `pytest tests/test_agent.py -q`.

Expected: PASS without network access.

- [ ] **Step 5: Commit the use case**

```bash
git add day6/backend/app/application/agent.py day6/backend/tests/test_agent.py
git commit -m "feat: implement first agent use case"
```

## Task 4: Add Settings and the DeepSeek Gateway Adapter

**Files:**
- Create: `day6/backend/app/infrastructure/settings.py`
- Create: `day6/backend/app/infrastructure/deepseek_gateway.py`
- Create: `day6/backend/tests/test_deepseek_gateway.py`

**Interfaces:**
- Consumes: `LLMGateway`, domain messages, and environment settings from Tasks 2-3.
- Produces: `DeepSeekGateway.complete(...) -> LLMResponse`.

- [ ] **Step 1: Write adapter tests using a fake SDK client**

The gateway constructor must accept an optional client so the test never contacts DeepSeek:

```python
import pytest
from app.infrastructure.deepseek_gateway import DeepSeekGateway


class FakeCompletions:
    async def create(self, **request):
        self.request = request
        return type("Completion", (), {
            "model": "deepseek-chat",
            "choices": [type("Choice", (), {
                "message": type("Message", (), {"content": "adapter answer"})()
            })()]
        })()


class FakeClient:
    def __init__(self):
        self.chat = type("Chat", (), {"completions": FakeCompletions()})()


@pytest.mark.asyncio
async def test_gateway_sends_openai_compatible_request():
    client = FakeClient()
    gateway = DeepSeekGateway(api_key="test", base_url="https://example.test/v1", model="deepseek-chat", client=client)

    response = await gateway.complete([])

    assert response.text == "adapter answer"
    assert client.chat.completions.request["model"] == "deepseek-chat"
```

Add mapping tests for `AuthenticationError`, `RateLimitError`, timeout, and connection failures by raising those SDK exceptions from a fake completion method and asserting the corresponding domain error.

- [ ] **Step 2: Run the adapter tests and verify failure**

Run `pytest tests/test_deepseek_gateway.py -q`.

Expected: FAIL because settings and adapter do not exist.

- [ ] **Step 3: Implement environment settings**

Use `pydantic-settings` with:

```python
class Settings(BaseSettings):
    deepseek_api_key: str
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
```

Environment variable names must be `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_MODEL`, `BACKEND_HOST`, and `BACKEND_PORT`.

- [ ] **Step 4: Implement the asynchronous DeepSeek adapter**

Create `AsyncOpenAI(api_key=..., base_url=..., timeout=30, max_retries=0)` when no test client is injected. Call `client.chat.completions.create` with the model and converted `{role, content}` messages, `temperature=0.7`, and no streaming.

Map provider errors without exposing raw details:

- `AuthenticationError` → `AuthenticationGatewayError`;
- `RateLimitError` → `RateLimitGatewayError`;
- `APITimeoutError` → `GatewayTimeoutError`;
- `APIConnectionError` → `LLMGatewayError`;
- empty content or unknown SDK errors → `LLMGatewayError`.

- [ ] **Step 5: Run adapter and Agent tests**

Run `pytest tests/test_deepseek_gateway.py tests/test_agent.py -q`.

Expected: PASS without a real API key.

- [ ] **Step 6: Commit the adapter**

```bash
git add day6/backend/app/infrastructure day6/backend/tests/test_deepseek_gateway.py
git commit -m "feat: add DeepSeek gateway adapter"
```

## Task 5: Expose the Agent Through FastAPI

**Files:**
- Create: `day6/backend/app/presentation/schemas.py`
- Create: `day6/backend/app/presentation/dependencies.py`
- Create: `day6/backend/app/presentation/routes.py`
- Create: `day6/backend/app/main.py`
- Modify: `day6/backend/tests/test_api.py`

**Interfaces:**
- Consumes: `Agent.run` and gateway error types from Tasks 3-4.
- Produces: `POST /api/chat` with request `{message: str}` and the documented response JSON.

- [ ] **Step 1: Write failing API tests**

Use `TestClient` and override the agent dependency with a fake Agent-like object. Cover success, blank/long input, authentication failure, rate limit, timeout, and unexpected failure.

The success assertion must verify:

```python
response.json() == {
    "answer": "fake answer",
    "model": "deepseek-chat",
    "duration_ms": 4,
    "stages": [
        {"name": "UI", "status": "completed"},
        {"name": "Agent", "status": "completed"},
        {"name": "DeepSeek API", "status": "completed"},
    ],
}
```

- [ ] **Step 2: Run the API tests to verify failure**

Run `pytest tests/test_api.py -q`.

Expected: FAIL because the FastAPI app and schemas do not exist.

- [ ] **Step 3: Implement request and response schemas**

Create `ChatRequest` with `message: str = Field(min_length=1, max_length=4000)`. Create `ChatResponse` with `answer`, `model`, `duration_ms`, and a list of `StageResponse` objects.

- [ ] **Step 4: Implement dependency injection**

Provide `get_agent() -> Agent` that is constructed once from `Settings` and `DeepSeekGateway`. Keep construction out of the route body so tests can replace it with `app.dependency_overrides[get_agent]`.

- [ ] **Step 5: Implement route and exception handlers**

The route must only:

1. receive `ChatRequest`;
2. call `await agent.run(request.message)`;
3. return `ChatResponse`.

Register handlers that map domain exceptions to:

- `InvalidUserMessage` → 422;
- `AuthenticationGatewayError` → 502 with API-key guidance;
- `RateLimitGatewayError` → 429 with retry guidance;
- `GatewayTimeoutError` → 504;
- `LLMGatewayError` → 502 with a generic provider message.

Do not include exception text, stack traces, keys, or provider payloads in JSON responses.

- [ ] **Step 6: Run API and full backend tests**

Run `pytest -q`.

Expected: all backend tests PASS without network access.

- [ ] **Step 7: Commit the HTTP layer**

```bash
git add day6/backend/app/presentation day6/backend/app/main.py day6/backend/tests/test_api.py
git commit -m "feat: expose agent through FastAPI"
```

## Task 6: Build the React Chat and Agent Flow UI

**Files:**
- Modify: `day6/frontend/src/App.jsx`
- Modify: `day6/frontend/src/main.jsx`
- Create: `day6/frontend/src/api.js`
- Create: `day6/frontend/src/components/ChatPanel.jsx`
- Create: `day6/frontend/src/components/AgentFlow.jsx`
- Create: `day6/frontend/src/styles.css`

**Interfaces:**
- Consumes: `POST /api/chat` response from Task 5.
- Produces: responsive hybrid interface with current prompt, answer, error, duration, and flow stages.

- [ ] **Step 1: Implement the API client**

Create:

```js
export async function askAgent(message) {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({message}),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || 'Не удалось получить ответ агента.');
  return payload;
}
```

- [ ] **Step 2: Implement the `AgentFlow` component**

Render the fixed labels `UI`, `Agent`, and `DeepSeek API`. Accept `stages` and `activeStage` props. Use the statuses `pending`, `active`, `completed`, and `error`; do not display model reasoning or raw provider data.

- [ ] **Step 3: Implement the `ChatPanel` component**

Render a controlled textarea, submit button, current user message, answer, loading state, and error state. Disable textarea and button while the request is active. Submit on Enter, while Shift+Enter inserts a newline.

- [ ] **Step 4: Compose `App` state and the local stage animation**

`App` owns:

- `message`;
- `answer`;
- `error`;
- `loading`;
- `result`;
- `stages`.

On submit, set local stages to `UI=completed`, `Agent=active`, `DeepSeek API=pending`; after the fetch resolves, replace them with response stages. On failure, mark `DeepSeek API=error` and show the safe message. This local animation is illustrative and must not be described as provider streaming.

- [ ] **Step 5: Add the responsive visual design**

Use a dark, high-contrast layout with a two-column desktop grid and one-column mobile breakpoint. Keep the chat as the primary panel and the flow diagram as the explanatory secondary panel. Add visible focus styles and readable error contrast.

- [ ] **Step 6: Build the frontend**

Run:

```bash
cd day6/frontend
npm run build
```

Expected: Vite completes successfully and creates `dist/`.

- [ ] **Step 7: Commit the frontend**

```bash
git add day6/frontend
git commit -m "feat: add day6 agent chat interface"
```

## Task 7: Add Documentation and Root Navigation

**Files:**
- Create: `day6/README.md`
- Modify: `README.md`

**Interfaces:**
- Documents the exact commands and boundaries produced by Tasks 1-6.

- [ ] **Step 1: Document the learning model**

`day6/README.md` must explain:

- an Agent is an application object that orchestrates a task, not a raw API call;
- FastAPI route receives HTTP but does not call DeepSeek;
- `LLMGateway` is the replaceable port;
- `DeepSeekGateway` is the infrastructure adapter;
- `FakeLLMGateway` makes tests independent of network and credentials;
- the request flow is `React → FastAPI → Agent → Gateway → DeepSeek → React`.

- [ ] **Step 2: Document setup and commands**

Include:

```bash
cd day6/backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

In a second terminal:

```bash
cd day6/frontend
npm install
npm run dev
```

Testing commands:

```bash
cd day6/backend
pytest -q
cd ../frontend
npm run build
```

- [ ] **Step 3: Add the root README entry**

Add:

```markdown
- [`day6`](./day6) — первый отдельный Python-агент с FastAPI, DeepSeek API и React-интерфейсом, показывающим поток запроса.
```

- [ ] **Step 4: Commit documentation**

```bash
git add README.md day6/README.md
git commit -m "docs: explain day6 first agent"
```

## Task 8: End-to-End Verification and Final Review

**Files:**
- Verify: `day6/backend/**`
- Verify: `day6/frontend/**`
- Verify: `day6/README.md`

- [ ] **Step 1: Run all backend checks without credentials**

Run `pytest -q` from `day6/backend` with no real API request.

Expected: all tests pass.

- [ ] **Step 2: Run frontend production build**

Run `npm run build` from `day6/frontend`.

Expected: build passes without warnings that indicate broken imports.

- [ ] **Step 3: Run the local integration manually**

With a local DeepSeek key in `day6/backend/.env`, start FastAPI and Vite. Send a question from the browser and verify:

- the browser sends only `{message}` to `/api/chat`;
- the response appears in the chat;
- the flow shows UI, Agent, and DeepSeek API stages;
- model and duration are visible;
- API key is absent from browser requests and rendered HTML;
- a deliberately blank submission is rejected;
- stopping or misconfiguring the provider produces a safe error card.

- [ ] **Step 4: Inspect the final diff**

Run:

```bash
git status --short
```

Confirm that `.env`, `.venv`, `node_modules`, and `frontend/dist` are ignored and no secret is staged.

- [ ] **Step 5: Make the final implementation commit**

Only after the previous checks pass:

```bash
git add day6
git commit -m "feat: complete day6 first agent"
```

## Plan Self-Review

- Spec coverage: the plan includes the separate Agent, gateway boundary, DeepSeek configuration, FastAPI endpoint, React chat, hybrid flow UI, safe error mapping, unit tests, API tests, frontend build, README, root navigation, and final verification.
- Placeholder scan: no `TBD`, `TODO`, or unspecified future implementation is required by a task.
- Type consistency: `Agent.run` consumes a string and returns `AgentResult`; `LLMGateway.complete` consumes `list[ChatMessage]` and returns `LLMResponse`; the FastAPI response serializes the same result fields; React consumes those JSON field names.
- Scope check: this is one cohesive first-agent subsystem. Memory, streaming, auth, persistence, and multi-agent orchestration are explicitly excluded.
