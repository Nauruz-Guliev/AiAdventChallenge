# День 8: подсчёт токенов и лимит контекста — план реализации

> **Для агентных исполнителей:** ТРЕБУЕТСЯ SUB-SKILL: использовать superpowers:executing-plans для реализации этого плана задачу за задачей. Шаги помечены чекбоксами (`- [ ]`).

**Цель:** добавить в приложение-копию day7 подсчёт токенов (текущий запрос, история, ответ модели), накопительную оценку стоимости и демонстрацию переполнения настраиваемого бюджета контекста.

**Архитектура:** day8 — самостоятельная копия day7. Локальная оценка токенов (tiktoken) разделяет «запрос» и «историю» и предсказывает переполнение до отправки; точный `usage` из ответа DeepSeek сохраняется с каждой парой сообщений в JSON и даёт накопительные токены/стоимость, переживающие рестарт. UI показывает прогресс-бар бюджета, статистику под каждым ответом и кнопку симуляции длинного диалога.

**Технологии:** Python 3.13, FastAPI, pydantic-settings, openai-SDK, tiktoken, pytest+pytest-asyncio; React + Vite.

## Глобальные ограничения

- `day6/` и `day7/` не изменяются ни на одном шаге.
- Секреты только в gitignored `day8/backend/.env`; `data/chats.json` gitignored.
- Все пользовательские строки и тексты ошибок — на русском.
- Финальная проверка бэкенда: `cd day8/backend && .venv/bin/pytest -q`; фронтенда: `cd day8/frontend && npm run build`.
- Каждый коммит — conventional (`feat:`/`fix:`/`docs:`/`chore:`), без push.
- Дефолты из спеки: `CONTEXT_LIMIT_TOKENS=8000`, цены worst-case: input `$0.30`/1M, output `$1.20`/1M (пик, cache miss, deepseek-flash).
- Локальные числа tiktoken везде помечаются как оценка (в коде, API и UI).

---

### Задача 1: Каркас day8 (копия day7)

**Файлы:**
- Создать: всё дерево `day8/` копированием из `day7/`
- Изменить: `day8/backend/requirements.txt`, `day8/backend/pyproject.toml`, `day8/frontend/package.json`, `day8/backend/app/main.py`

**Интерфейсы:**
- Produces: рабочий каркас с зелёными тестами day7 (28 passed).

- [ ] **Шаг 1. Скопировать каркас без артефактов**

```bash
cd /Users/nauruz/AIADVENTCHALLENGE
rsync -a --exclude '.venv' --exclude 'node_modules' --exclude 'dist' \
  --exclude '__pycache__' --exclude '.pytest_cache' --exclude '.env' \
  --exclude 'data/' day7/ day8/
mkdir -p day8/backend/data
cp day7/backend/.env day8/backend/.env
```

- [ ] **Шаг 2. Переименовать проект и заголовок приложения**

`day8/backend/requirements.txt` — дописать строку:

```
tiktoken>=0.9,<1
```

`day8/backend/pyproject.toml` — заменить `name = "advent-challenge-day6-backend"` на `name = "advent-challenge-day8-backend"`.

`day8/frontend/package.json` — заменить `"name": "advent-challenge-day6-frontend"` на `"name": "advent-challenge-day8-frontend"`.

`day8/backend/app/main.py` — заменить `title="Day 7 Context Persistence"` на `title="Day 8 Token Counting"`.

- [ ] **Шаг 3. Установить зависимости**

```bash
cd /Users/nauruz/AIADVENTCHALLENGE/day8/backend && python3.13 -m venv .venv && .venv/bin/pip install -r requirements.txt
cd /Users/nauruz/AIADVENTCHALLENGE/day8/frontend && npm install
```
Ожидается: успешная установка без ошибок.

- [ ] **Шаг 4. Прогнать перенесённые тесты**

```bash
cd /Users/nauruz/AIADVENTCHALLENGE/day8/backend && .venv/bin/pytest -q
```
Ожидается: `28 passed`.

- [ ] **Шаг 5. Проверить gitignore и закоммитить**

```bash
cd /Users/nauruz/AIADVENTCHALLENGE
git check-ignore day8/backend/.env day8/backend/data/chats.json 2>/dev/null; true
git check-ignore -q day8/backend/.env
git status --short | head -20
git add day8 && git commit -m "feat: scaffold day8 token counting"
```
Ожидается: `.env` игнорируется; в `git status` до коммита только файлы `day8/`.

---

### Задача 2: Доменные модели токенов и локальный счётчик

**Файлы:**
- Создать: `day8/backend/app/application/ports/token_counter.py`, `day8/backend/app/infrastructure/token_counter.py`, `day8/backend/tests/test_token_counter.py`
- Изменить: `day8/backend/app/domain/models.py`, `day8/backend/tests/test_agent.py`, `day8/backend/tests/test_chat_api.py`, `day8/backend/tests/test_deepseek_gateway.py`

**Интерфейсы:**
- Produces:
  - `TokenUsage(prompt_tokens: int, completion_tokens: int, total_tokens: int)`
  - `UsageConfig(context_limit_tokens: int = 8000, input_price_per_million: float = 0.30, output_price_per_million: float = 1.20)`
  - `DialogUsage(history_tokens: int, dialog_total_tokens: int, dialog_cost_usd: float, context_limit: int, context_remaining: int, warning: bool)`
  - `UsageReport(request_tokens, history_tokens, response_tokens, prompt_tokens_api, completion_tokens_api, total_tokens_api, dialog_total_tokens, dialog_cost_usd, context_limit, context_remaining, warning)` — все ints, кроме `dialog_cost_usd: float`, `warning: bool`
  - `ContextLimitExceeded(estimated_tokens: int = 0, context_limit: int = 0)` c атрибутами
  - `ChatMessage.usage: TokenUsage | None = None`; `LLMResponse.usage: TokenUsage` (обязательное); `AgentResult.usage: UsageReport` (обязательное)
  - `TiktokenCounter.count_text(text: str) -> int`, `TiktokenCounter.count_messages(messages: list[ChatMessage]) -> int`, константа `PER_MESSAGE_OVERHEAD_TOKENS = 4`
  - протокол `TokenCounter` в `app/application/ports/token_counter.py`

- [ ] **Шаг 1. Написать падающие тесты счётчика**

`day8/backend/tests/test_token_counter.py`:

```python
from app.domain.models import ChatMessage
from app.infrastructure.token_counter import PER_MESSAGE_OVERHEAD_TOKENS, TiktokenCounter


def test_count_text_returns_zero_for_empty_string():
    assert TiktokenCounter().count_text("") == 0


def test_count_text_counts_known_english_phrase():
    assert TiktokenCounter().count_text("hello world") == 2


def test_count_text_counts_russian_text_more_than_words():
    assert TiktokenCounter().count_text("сколько стоит контекст") > 4


def test_count_messages_adds_per_message_overhead():
    counter = TiktokenCounter()
    messages = [
        ChatMessage(role="system", content="hello world"),
        ChatMessage(role="user", content="hello world"),
    ]

    assert counter.count_messages(messages) == 2 * (
        2 + PER_MESSAGE_OVERHEAD_TOKENS
    )
```

- [ ] **Шаг 2. Убедиться, что тесты падают**

Run: `cd day8/backend && .venv/bin/pytest tests/test_token_counter.py -q`
Ожидается: FAIL (`No module named 'app.infrastructure.token_counter'`).

- [ ] **Шаг 3. Реализовать счётчик**

`day8/backend/app/infrastructure/token_counter.py`:

```python
import tiktoken

from app.domain.models import ChatMessage

PER_MESSAGE_OVERHEAD_TOKENS = 4


class TiktokenCounter:
    """Локальная оценка токенов.

    У DeepSeek собственный токенизатор, cl100k_base даёт приближение,
    поэтому все числа из этого класса — оценка, а не биллинг.
    """

    def __init__(self, encoding_name: str = "cl100k_base"):
        self._encoding = tiktoken.get_encoding(encoding_name)

    def count_text(self, text: str) -> int:
        return len(self._encoding.encode(text))

    def count_messages(self, messages: list[ChatMessage]) -> int:
        return sum(
            self.count_text(message.content) + PER_MESSAGE_OVERHEAD_TOKENS
            for message in messages
        )
```

`day8/backend/app/application/ports/token_counter.py`:

```python
from typing import Protocol

from app.domain.models import ChatMessage


class TokenCounter(Protocol):
    def count_text(self, text: str) -> int: ...

    def count_messages(self, messages: list[ChatMessage]) -> int: ...
```

- [ ] **Шаг 4. Расширить доменные модели**

В `day8/backend/app/domain/models.py` после импортов добавить датаклассы и заменить определения:

```python
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
```

`ChatMessage` дополнить полем (после `content`): `usage: TokenUsage | None = None`.
`LLMResponse` дополнить обязательным полем: `usage: TokenUsage`.
`AgentResult` дополнить обязательным полем: `usage: UsageReport`.
В секцию ошибок добавить:

```python
class ContextLimitExceeded(RuntimeError):
    def __init__(self, estimated_tokens: int = 0, context_limit: int = 0):
        super().__init__(f"Context limit exceeded: {estimated_tokens}/{context_limit}")
        self.estimated_tokens = estimated_tokens
        self.context_limit = context_limit
```

- [ ] **Шаг 5. Починить существующие тесты под новые обязательные поля**

Во всех трёх файлах тестов (`test_agent.py`, `test_chat_api.py`, `test_deepseek_gateway.py`) создать один и тот же помощник и подставить его в конструкторы:

```python
def sample_usage() -> TokenUsage:
    return TokenUsage(prompt_tokens=100, completion_tokens=20, total_tokens=120)


def sample_report() -> UsageReport:
    return UsageReport(
        request_tokens=8,
        history_tokens=120,
        response_tokens=20,
        prompt_tokens_api=128,
        completion_tokens_api=20,
        total_tokens_api=148,
        dialog_total_tokens=148,
        dialog_cost_usd=0.00042,
        context_limit=8000,
        context_remaining=7872,
        warning=False,
    )
```

Замены:
- `test_agent.py`: `AgentResult(...)` → добавить `usage=sample_report()`; `LLMResponse(text="hello", model="deepseek-chat")` → добавить `usage=sample_usage()`; `FakeGateway.__init__` дефолт → `LLMResponse("fake answer", "deepseek-chat", sample_usage())`.
- `test_chat_api.py`: `AgentResult(...)` в `FakeAgent.run` → добавить `usage=sample_report()`.
- `test_deepseek_gateway.py`: импорт `TokenUsage, UsageReport` и хелперы; фиктивная completion в тесте `test_gateway_sends_openai_compatible_request` пока вернёт `.usage=None` — этот тест обновится в задаче 4, поэтому здесь только хелперы и импорты (чтобы файл компилировался). В `test_agent_sends_previous_history_and_saves_exchange` ассистентское сообщение истории `ChatMessage(role="assistant", content="Приятно познакомиться")` оставить без usage (дефолт None).

- [ ] **Шаг 6. Прогнать весь бэкенд**

Run: `cd day8/backend && .venv/bin/pytest -q`
Ожидается: все тесты `passed` (28 + 4 новых).

- [ ] **Шаг 7. Закоммитить**

```bash
git add day8/backend && git commit -m "feat: add token domain models and tiktoken counter"
```

---

### Задача 3: Хелперы накопительной статистики диалога

**Файлы:**
- Создать: `day8/backend/app/application/usage.py`, `day8/backend/tests/test_usage.py`

**Интерфейсы:**
- Consumes: `TokenUsage`, `DialogUsage`, `UsageConfig`, протокол `TokenCounter` (задача 2)
- Produces:
  - `exchange_cost_usd(usage: TokenUsage, config: UsageConfig) -> float`
  - `build_dialog_usage(messages: list[ChatMessage], counter: TokenCounter, config: UsageConfig) -> DialogUsage`
  - константа `WARNING_FILL_RATIO = 0.8`

- [ ] **Шаг 1. Написать падающие тесты**

`day8/backend/tests/test_usage.py`:

```python
import pytest

from app.application.usage import WARNING_FILL_RATIO, build_dialog_usage, exchange_cost_usd
from app.domain.models import ChatMessage, TokenUsage, UsageConfig
from app.infrastructure.token_counter import TiktokenCounter


def msg(role, content, usage=None):
    return ChatMessage(role=role, content=content, usage=usage)


def test_exchange_cost_uses_worst_case_prices():
    usage = TokenUsage(prompt_tokens=1_000_000, completion_tokens=500_000, total_tokens=1_500_000)

    cost = exchange_cost_usd(usage, UsageConfig())

    assert cost == pytest.approx(0.30 + 0.60)


def test_build_dialog_usage_accumulates_persisted_usage():
    messages = [
        msg("system", "Вы полезный ассистент."),
        msg("user", "Меня зовут Анна"),
        msg("assistant", "Приятно познакомиться", TokenUsage(50, 10, 60)),
        msg("user", "Как меня зовут?"),
        msg("assistant", "Вас зовут Анна.", TokenUsage(70, 12, 82)),
    ]

    dialog = build_dialog_usage(messages, TiktokenCounter(), UsageConfig())

    assert dialog.dialog_total_tokens == 142
    assert dialog.dialog_cost_usd == pytest.approx(
        exchange_cost_usd(TokenUsage(50, 10, 60), UsageConfig())
        + exchange_cost_usd(TokenUsage(70, 12, 82), UsageConfig())
    )
    assert dialog.history_tokens > 0
    assert dialog.context_limit == 8000
    assert dialog.context_remaining == 8000 - dialog.history_tokens
    assert dialog.warning is False


def test_build_dialog_usage_warns_near_limit():
    filler = "токен " * 4000
    messages = [msg("user", filler)]
    config = UsageConfig(context_limit_tokens=3000)

    dialog = build_dialog_usage(messages, TiktokenCounter(), config)

    assert dialog.history_tokens >= config.context_limit_tokens * WARNING_FILL_RATIO
    assert dialog.warning is True


def test_dialog_without_usage_has_zero_totals():
    messages = [msg("system", "Вы полезный ассистент."), msg("user", "Привет")]

    dialog = build_dialog_usage(messages, TiktokenCounter(), UsageConfig())

    assert dialog.dialog_total_tokens == 0
    assert dialog.dialog_cost_usd == 0.0
```

- [ ] **Шаг 2. Убедиться, что падают**

Run: `cd day8/backend && .venv/bin/pytest tests/test_usage.py -q`
Ожидается: FAIL (`No module named 'app.application.usage'`).

- [ ] **Шаг 3. Реализовать хелперы**

`day8/backend/app/application/usage.py`:

```python
from app.application.ports.token_counter import TokenCounter
from app.domain.models import ChatMessage, DialogUsage, TokenUsage, UsageConfig

WARNING_FILL_RATIO = 0.8


def exchange_cost_usd(usage: TokenUsage, config: UsageConfig) -> float:
    return (
        usage.prompt_tokens * config.input_price_per_million
        + usage.completion_tokens * config.output_price_per_million
    ) / 1_000_000


def build_dialog_usage(
    messages: list[ChatMessage],
    counter: TokenCounter,
    config: UsageConfig,
) -> DialogUsage:
    history_tokens = counter.count_messages(messages)
    exchanges = [message.usage for message in messages if message.usage is not None]
    remaining = config.context_limit_tokens - history_tokens
    return DialogUsage(
        history_tokens=history_tokens,
        dialog_total_tokens=sum(usage.total_tokens for usage in exchanges),
        dialog_cost_usd=sum(exchange_cost_usd(usage, config) for usage in exchanges),
        context_limit=config.context_limit_tokens,
        context_remaining=max(remaining, 0),
        warning=history_tokens >= config.context_limit_tokens * WARNING_FILL_RATIO,
    )
```

- [ ] **Шаг 4. Прогнать тесты**

Run: `cd day8/backend && .venv/bin/pytest tests/test_usage.py -q`
Ожидается: PASS (4).

- [ ] **Шаг 5. Закоммитить**

```bash
git add day8/backend && git commit -m "feat: add dialog usage aggregation helpers"
```

---

### Задача 4: Gateway — точный usage из API и маппинг ошибки 400

**Файлы:**
- Изменить: `day8/backend/app/domain/models.py` (без правок — только использовать), `day8/backend/app/infrastructure/deepseek_gateway.py`, `day8/backend/tests/test_deepseek_gateway.py`

**Интерфейсы:**
- Consumes: `TokenUsage`, `ContextLimitExceeded`, `LLMGatewayError`
- Produces: `LLMGateway.complete(messages) -> LLMResponse` теперь заполняет `response.usage`

- [ ] **Шаг 1. Обновить фиктивного клиента и написать падающие тесты**

В `day8/backend/tests/test_deepseek_gateway.py`: импорт `from openai import BadRequestError`, `from app.domain.models import ContextLimitExceeded, TokenUsage` (хелперы `sample_usage` уже есть). Заменить фиктивную `completion()`:

```python
def completion(text="adapter answer", model="deepseek-chat", usage="default"):
    usage_object = (
        type("Usage", (), {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        })()
        if usage == "default"
        else usage
    )
    return type("Completion", (), {
        "model": model,
        "usage": usage_object,
        "choices": [type("Choice", (), {
            "message": type("Message", (), {"content": text})(),
        })()],
    })()
```

Добавить тесты:

```python
@pytest.mark.asyncio
async def test_gateway_returns_token_usage():
    client = FakeClient(completion())
    gateway = DeepSeekGateway(client=client)

    response = await gateway.complete([ChatMessage(role="user", content="hello")])

    assert response.usage == TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)


@pytest.mark.asyncio
async def test_gateway_rejects_response_without_usage():
    gateway = DeepSeekGateway(client=FakeClient(completion(usage=None)))

    with pytest.raises(LLMGatewayError):
        await gateway.complete([ChatMessage(role="user", content="hello")])


@pytest.mark.asyncio
async def test_gateway_maps_context_length_error():
    error = BadRequestError(
        "context_length_exceeded: maximum context length exceeded",
        response=error_response(400),
        body={"error": {"code": "context_length_exceeded"}},
    )

    with pytest.raises(ContextLimitExceeded):
        await DeepSeekGateway(client=FakeClient(error=error)).complete([])


@pytest.mark.asyncio
async def test_gateway_maps_other_bad_requests_to_gateway_error():
    error = BadRequestError(
        "invalid_request_error: unknown field",
        response=error_response(400),
        body={"error": {"code": "invalid_request_error"}},
    )

    with pytest.raises(LLMGatewayError):
        await DeepSeekGateway(client=FakeClient(error=error)).complete([])
```

Также в `test_gateway_sends_openai_compatible_request` добавить `assert response.usage.total_tokens == 15`.

- [ ] **Шаг 2. Убедиться, что падают**

Run: `cd day8/backend && .venv/bin/pytest tests/test_deepseek_gateway.py -q`
Ожидается: 4 новых FAIL.

- [ ] **Шаг 3. Реализовать**

В `day8/backend/app/infrastructure/deepseek_gateway.py` расширить импорты (`BadRequestError` из openai; `ContextLimitExceeded`, `TokenUsage` из domain) и изменить `complete`:

```python
        except BadRequestError as error:
            if _is_context_length_error(error):
                raise ContextLimitExceeded() from error
            raise LLMGatewayError from error
```
(разместить перед `except Exception`), после извлечения текста:

```python
        usage = completion.usage
        if usage is None:
            raise LLMGatewayError("Provider returned no token usage")

        return LLMResponse(
            text=text,
            model=completion.model or self._model,
            usage=TokenUsage(
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
            ),
        )
```

Добавить в конец модуля:

```python
def _is_context_length_error(error: BadRequestError) -> bool:
    body = error.body if isinstance(error.body, dict) else {}
    code = body.get("error", {}).get("code") if isinstance(body.get("error"), dict) else None
    return code == "context_length_exceeded" or "context_length_exceeded" in str(error)
```

- [ ] **Шаг 4. Прогнать тесты файла**

Run: `cd day8/backend && .venv/bin/pytest tests/test_deepseek_gateway.py -q`
Ожидается: PASS.

- [ ] **Шаг 5. Закоммитить**

```bash
git add day8/backend && git commit -m "feat: capture token usage in deepseek gateway"
```

---

### Задача 5: Репозиторий — сохранение usage + сквозной проход через agent

**Файлы:**
- Изменить: `day8/backend/app/application/ports/chat_repository.py`, `day8/backend/app/infrastructure/json_chat_repository.py`, `day8/backend/app/application/agent.py`, `day8/backend/tests/test_json_chat_repository.py`, `day8/backend/tests/test_agent.py`

**Интерфейсы:**
- Consumes: `TokenUsage`
- Produces: `ChatRepository.append_exchange(chat_id, user_content, assistant_content, usage: TokenUsage)`; usage сериализуется в assistant-сообщение JSON-хранилища и восстанавливается в `ChatMessage.usage`

- [ ] **Шаг 1. Обновить существующие тесты репозитория и добавить падающие**

В `test_json_chat_repository.py`: импорт `TokenUsage`; все вызовы `append_exchange(chat.id, "...", "...")` → `append_exchange(chat.id, "...", "...", TokenUsage(10, 5, 15))`. Добавить:

```python
@pytest.mark.asyncio
async def test_assistant_message_persists_and_restores_usage(tmp_path):
    repository = JsonChatRepository(tmp_path / "chats.json")
    chat = await repository.create_chat()
    usage = TokenUsage(prompt_tokens=33, completion_tokens=7, total_tokens=40)

    await repository.append_exchange(chat.id, "Вопрос", "Ответ", usage)

    restored = await JsonChatRepository(tmp_path / "chats.json").get_chat(chat.id)
    assert restored.messages[0].usage is None
    assert restored.messages[1].usage == usage


@pytest.mark.asyncio
async def test_storage_without_usage_field_loads_none(tmp_path):
    path = tmp_path / "chats.json"
    path.write_text(
        '{"version": 1, "chats": [{"id": "chat-1", "title": "Т", '
        '"created_at": "2026-09-14T00:00:00+00:00", "updated_at": "2026-09-14T00:00:00+00:00", '
        '"messages": [{"role": "assistant", "content": "ok"}]}]}',
        encoding="utf-8",
    )

    chat = await JsonChatRepository(path).get_chat("chat-1")

    assert chat.messages[0].usage is None
```

- [ ] **Шаг 2. Убедиться, что падают**

Run: `cd day8/backend && .venv/bin/pytest tests/test_json_chat_repository.py -q`
Ожидается: TypeError/`got an unexpected keyword argument` или assert-ошибки.

- [ ] **Шаг 3. Реализовать протокол, хранилище и сквозной проход**

В `chat_repository.py` протокол: `async def append_exchange(self, chat_id: str, user_content: str, assistant_content: str, usage: TokenUsage) -> Chat: ...` (импорт `TokenUsage`).

В `json_chat_repository.py`: параметр `usage: TokenUsage` в `append_exchange`; assistant-словарь в `extend`:

```python
                        {
                            "role": "assistant",
                            "content": assistant_content,
                            "usage": {
                                "prompt_tokens": usage.prompt_tokens,
                                "completion_tokens": usage.completion_tokens,
                                "total_tokens": usage.total_tokens,
                            },
                        },
```

В `_chat_from_dict` строить сообщения так, чтобы `usage=None`, когда ключа нет:

```python
        messages=[
            ChatMessage(
                role=message["role"],
                content=message["content"],
                usage=(
                    TokenUsage(**message["usage"]) if message.get("usage") else None
                ),
            )
            for message in stored_chat["messages"]
        ],
```
(импорт `TokenUsage`). В `_chat_to_dict` — то же чтение `usage` в dict-форму с проверкой `message.usage`.

В `agent.py`: временно пробросить `usage=response.usage` в `append_exchange`, НЕ менять остальную логику (полный `UsageReport` — задача 6). В `test_agent.py`: `FakeRepository.append_exchange(self, chat_id, user_content, assistant_content, usage)` и `self.saved = (chat_id, user_content, assistant_content, usage)`; в `test_agent_sends_previous_history_and_saves_exchange` ожидание `repository.saved == ("chat-1", "Как меня зовут?", result.answer, response.usage)` — проще хранить `usage` и сравнивать `repository.saved[:3]` с прежней тройкой и `repository.saved[3] == sample_usage()`.

- [ ] **Шаг 4. Прогнать весь бэкенд**

Run: `cd day8/backend && .venv/bin/pytest -q`
Ожидается: все PASS.

- [ ] **Шаг 5. Закоммитить**

```bash
git add day8/backend && git commit -m "feat: persist token usage with each assistant message"
```

---

### Задача 6: Agent — бюджет контекста, pre-check и UsageReport

**Файлы:**
- Изменить: `day8/backend/app/application/agent.py`, `day8/backend/app/presentation/dependencies.py` (только конструктор Agent), `day8/backend/tests/test_agent.py`

**Интерфейсы:**
- Consumes: `TiktokenCounter`/`TokenCounter`, `UsageConfig`, `build_dialog_usage`, `DialogUsage`, `UsageReport`, `ContextLimitExceeded`
- Produces: `Agent(gateway, repository, counter, config, model="deepseek-chat")`; `Agent.run` бросает `ContextLimitExceeded(estimated, limit)` до вызова gateway и до записи; `AgentResult.usage` заполнен

- [ ] **Шаг 1. Переписать тесты agent целиком (падающие)**

Заменить `day8/backend/tests/test_agent.py` на:

```python
import pytest

from app.application.agent import Agent
from app.domain.models import (
    AgentResult,
    AgentStage,
    Chat,
    ChatMessage,
    ContextLimitExceeded,
    InvalidUserMessage,
    LLMGatewayError,
    LLMResponse,
    TokenUsage,
    UsageConfig,
    UsageReport,
)
from app.infrastructure.token_counter import TiktokenCounter


def sample_usage() -> TokenUsage:
    return TokenUsage(prompt_tokens=100, completion_tokens=20, total_tokens=120)


def sample_report() -> UsageReport:
    return UsageReport(
        request_tokens=8,
        history_tokens=120,
        response_tokens=20,
        prompt_tokens_api=128,
        completion_tokens_api=20,
        total_tokens_api=148,
        dialog_total_tokens=148,
        dialog_cost_usd=0.00042,
        context_limit=8000,
        context_remaining=7872,
        warning=False,
    )


class FakeGateway:
    def __init__(self, response=None, error=None):
        self.response = response or LLMResponse(
            "fake answer", "deepseek-chat", sample_usage()
        )
        self.error = error
        self.messages = None

    async def complete(self, messages):
        self.messages = messages
        if self.error:
            raise self.error
        return self.response


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

    async def append_exchange(self, chat_id, user_content, assistant_content, usage):
        self.saved = (chat_id, user_content, assistant_content, usage)
        return self.chat


def make_agent(gateway=None, repository=None, config=None):
    return Agent(
        gateway or FakeGateway(),
        repository or FakeRepository(),
        counter=TiktokenCounter(),
        config=config or UsageConfig(),
    )


@pytest.mark.asyncio
async def test_agent_sends_previous_history_and_saves_exchange():
    gateway = FakeGateway()
    repository = FakeRepository()

    result = await make_agent(gateway, repository).run("chat-1", "Как меня зовут?")

    assert [message.role for message in gateway.messages] == [
        "system", "user", "assistant", "user",
    ]
    assert gateway.messages[-1].content == "Как меня зовут?"
    assert repository.saved[:3] == ("chat-1", "Как меня зовут?", result.answer)
    assert repository.saved[3] == sample_usage()


@pytest.mark.asyncio
async def test_agent_returns_usage_report_split_and_totals():
    result = await make_agent().run("chat-1", "Как меня зовут?")

    usage = result.usage
    assert usage.request_tokens > 0
    assert usage.history_tokens > 0
    assert usage.response_tokens == 20
    assert usage.prompt_tokens_api == 100
    assert usage.total_tokens_api == 120
    assert usage.dialog_total_tokens == 120
    assert usage.dialog_cost_usd == pytest.approx((100 * 0.30 + 20 * 1.20) / 1_000_000)
    assert usage.context_limit == 8000
    assert 0 < usage.context_remaining < 8000


@pytest.mark.asyncio
async def test_agent_blocks_request_over_context_budget():
    gateway = FakeGateway()
    repository = FakeRepository()
    huge_history = Chat(
        id="chat-1",
        title="Длинный",
        created_at="2026-09-13T12:00:00+00:00",
        updated_at="2026-09-13T12:00:00+00:00",
        messages=[
            ChatMessage(role="user", content="токен " * 3000),
            ChatMessage(role="assistant", content="ok"),
        ],
    )

    class BigChatRepository(FakeRepository):
        async def get_chat(self, chat_id):
            return huge_history

    agent = make_agent(
        gateway, BigChatRepository(), config=UsageConfig(context_limit_tokens=2000)
    )

    with pytest.raises(ContextLimitExceeded) as excinfo:
        await agent.run("chat-1", "Привет")

    assert excinfo.value.estimated_tokens > 2000
    assert excinfo.value.context_limit == 2000
    assert gateway.messages is None
    assert repository.saved is None


@pytest.mark.asyncio
async def test_agent_warning_when_budget_nearly_full():
    repository = FakeRepository()
    filler = ChatMessage(role="user", content="токен " * 1300)
    repository.chat = Chat(
        id="chat-1",
        title="Почти полный",
        created_at="2026-09-13T12:00:00+00:00",
        updated_at="2026-09-13T12:00:00+00:00",
        messages=[filler],
    )

    result = await make_agent(
        FakeGateway(), repository, config=UsageConfig(context_limit_tokens=2500)
    ).run("chat-1", "Привет")

    assert result.usage.warning is True


@pytest.mark.asyncio
async def test_agent_sends_user_message_and_returns_answer():
    gateway = FakeGateway()

    result = await make_agent(gateway).run("chat-1", "  hello  ")

    assert result.answer == "fake answer"
    assert gateway.messages[-1].content == "hello"
    assert [stage.status for stage in result.stages] == ["completed"] * 3


@pytest.mark.asyncio
async def test_agent_rejects_blank_message():
    with pytest.raises(InvalidUserMessage):
        await make_agent().run("chat-1", "   ")


@pytest.mark.asyncio
async def test_agent_preserves_gateway_error():
    with pytest.raises(LLMGatewayError):
        await make_agent(
            FakeGateway(error=LLMGatewayError("provider failed")),
        ).run("chat-1", "hello")


@pytest.mark.asyncio
async def test_over_budget_message_is_not_saved():
    repository = FakeRepository()
    repository.chat = Chat(
        id="chat-1",
        title="Т",
        created_at="2026-09-13T12:00:00+00:00",
        updated_at="2026-09-13T12:00:00+00:00",
        messages=[ChatMessage(role="user", content="токен " * 1400)],
    )

    with pytest.raises(ContextLimitExceeded):
        await make_agent(
            FakeGateway(), repository, config=UsageConfig(context_limit_tokens=1500)
        ).run("chat-1", "Привет ещё раз")

    assert repository.saved is None
```

- [ ] **Шаг 2. Убедиться, что падают**

Run: `cd day8/backend && .venv/bin/pytest tests/test_agent.py -q`
Ожидается: FAIL (`Agent.__init__() got an unexpected keyword argument 'counter'` и др.)

- [ ] **Шаг 3. Переписать `agent.py`**

Полный новый `run` (поля `SYSTEM_PROMPT`, `MAX_MESSAGE_LENGTH`, `_validate_message` не меняются; конструктор и `run`):

```python
    def __init__(
        self,
        gateway: LLMGateway,
        repository: ChatRepository,
        counter: TokenCounter,
        config: UsageConfig,
        model: str = "deepseek-chat",
    ):
        self._gateway = gateway
        self._repository = repository
        self._counter = counter
        self._config = config
        self._model = model

    async def run(self, chat_id: str, user_text: str) -> AgentResult:
        message = self._validate_message(user_text)
        chat = await self._repository.get_chat(chat_id)

        system_message = ChatMessage(role="system", content=SYSTEM_PROMPT)
        history_messages = [system_message, *chat.messages]
        new_message = ChatMessage(role="user", content=message)
        history_tokens = self._counter.count_messages(history_messages)
        request_tokens = self._counter.count_messages([new_message])
        estimated = history_tokens + request_tokens
        if estimated > self._config.context_limit_tokens:
            raise ContextLimitExceeded(estimated, self._config.context_limit_tokens)

        started_at = perf_counter()
        response = await self._gateway.complete([*history_messages, new_message])
        answer = response.text.strip()
        updated_chat = await self._repository.append_exchange(
            chat_id, message, answer, response.usage
        )

        dialog = build_dialog_usage(
            [system_message, *updated_chat.messages],
            self._counter,
            self._config,
        )
        usage = UsageReport(
            request_tokens=request_tokens,
            history_tokens=history_tokens,
            response_tokens=response.usage.completion_tokens,
            prompt_tokens_api=response.usage.prompt_tokens,
            completion_tokens_api=response.usage.completion_tokens,
            total_tokens_api=response.usage.total_tokens,
            dialog_total_tokens=dialog.dialog_total_tokens,
            dialog_cost_usd=dialog.dialog_cost_usd,
            context_limit=dialog.context_limit,
            context_remaining=dialog.context_remaining,
            warning=dialog.warning,
        )
        return AgentResult(
            answer=answer,
            model=response.model or self._model,
            duration_ms=round((perf_counter() - started_at) * 1000),
            stages=[
                AgentStage(name="UI", status="completed"),
                AgentStage(name="Agent", status="completed"),
                AgentStage(name="DeepSeek API", status="completed"),
            ],
            usage=usage,
        )
```

Импорты дополнить: `ContextLimitExceeded`, `UsageConfig`, `UsageReport` из domain; `TokenCounter` из ports; `build_dialog_usage` из `app.application.usage`.

- [ ] **Шаг 4. Обновить провайдер зависимостей**

`dependencies.py` — временно, чтобы приложение собиралось: в `get_agent` передать `counter=TiktokenCounter(), config=UsageConfig()` (импорты из infrastructure/domain). Полноценный wiring из `Settings` — задача 7.

- [ ] **Шаг 5. Прогнать весь бэкенд**

Run: `cd day8/backend && .venv/bin/pytest -q`
Ожидается: все PASS (ожидаемо ~38).

- [ ] **Шаг 6. Закоммитить**

```bash
git add day8/backend && git commit -m "feat: enforce context budget and report usage in agent"
```

---

### Задача 7: API — usage в ответах, 413 и dialog_usage

**Файлы:**
- Изменить: `day8/backend/app/infrastructure/settings.py`, `day8/backend/app/presentation/dependencies.py`, `day8/backend/app/presentation/schemas.py`, `day8/backend/app/presentation/routes.py`, `day8/backend/app/main.py`, `day8/backend/tests/test_chat_api.py`, `day8/backend/.env.example`

**Интерфейсы:**
- Consumes: `UsageReport`, `DialogUsage`, `build_dialog_usage`, `SYSTEM_PROMPT`, `ContextLimitExceeded`
- Produces: `Settings.context_limit_tokens/input_price_per_million/output_price_per_million`; `get_usage_config()`; HTTP 413 `{detail, estimated_tokens, context_limit}`; `ChatResponse.usage`; `ChatMessageResponse.usage`; `ChatDetailResponse.dialog_usage`

- [ ] **Шаг 1. Написать падающие API-тесты**

В `test_chat_api.py`: хелперы `sample_usage()`/`sample_report()` уже есть после задачи 5 — `FakeAgent` возвращает `AgentResult(..., usage=sample_report())`. В `FakeRepository.chat` assistant-сообщение получать usage: `ChatMessage(role="assistant", content="Приятно познакомиться", usage=sample_usage())`. Импорт `ContextLimitExceeded`, `UsageConfig`.

Обновить/добавить тесты:

```python
def test_send_message_returns_usage_breakdown(client):
    response = client[0].post(
        "/api/chats/chat-1/messages",
        json={"message": "Как меня зовут?"},
    )

    assert response.status_code == 200
    usage = response.json()["usage"]
    assert usage["request_tokens"] == 8
    assert usage["history_tokens"] == 120
    assert usage["response_tokens"] == 20
    assert usage["prompt_tokens_api"] == 128
    assert usage["dialog_total_tokens"] == 148
    assert usage["context_limit"] == 8000
    assert usage["warning"] is False


def test_get_chat_returns_message_and_dialog_usage(client):
    response = client[0].get("/api/chats/chat-1")

    payload = response.json()
    assert payload["messages"][0]["usage"] is None
    assert payload["messages"][1]["usage"] == {
        "prompt_tokens": 100,
        "completion_tokens": 20,
        "total_tokens": 120,
    }
    dialog = payload["dialog_usage"]
    assert dialog["dialog_total_tokens"] == 120
    assert dialog["context_limit"] == 8000
    assert dialog["history_tokens"] > 0
    assert 0 <= dialog["context_remaining"] < 8000


def test_send_message_over_budget_returns_413_without_answer(client):
    fake_agent = FakeAgent(
        error=ContextLimitExceeded(estimated_tokens=8400, context_limit=8000)
    )
    app.dependency_overrides[get_agent] = lambda: fake_agent

    response = client[0].post(
        "/api/chats/chat-1/messages",
        json={"message": "привет"},
    )

    assert response.status_code == 413
    assert response.json()["estimated_tokens"] == 8400
    assert response.json()["context_limit"] == 8000
    assert "превысил лимит контекста" in response.json()["detail"]


def test_over_budget_error_body_detail_mentions_new_chat(client):
    fake_agent = FakeAgent(
        error=ContextLimitExceeded(estimated_tokens=8400, context_limit=8000)
    )
    app.dependency_overrides[get_agent] = lambda: fake_agent

    response = client[0].post(
        "/api/chats/chat-1/messages",
        json={"message": "привет"},
    )

    assert "новый чат" in response.json()["detail"].lower()
```

`test_get_chat_returns_history` из старого набора остаётся, но ожидание `messages` теперь содержит ключ `usage` — обновить сравнение: user → `"usage": None`, assistant → `None` не пройдёт (tam usage добавлен в FakeRepository выше); поэтому в этом тесте сравнивать только `role/content`:

```python
    assert [
        {"role": m["role"], "content": m["content"]}
        for m in response.json()["messages"]
    ] == [
        {"role": "user", "content": "Меня зовут Анна"},
        {"role": "assistant", "content": "Приятно познакомиться"},
    ]
```

- [ ] **Шаг 2. Убедиться, что падают**

Run: `cd day8/backend && .venv/bin/pytest tests/test_chat_api.py -q`
Ожидается: новые FAIL (422/KeyError «usage»/отсутствие 413-хендлера).

- [ ] **Шаг 3. Settings + dependencies + env.example**

`settings.py` добавить поля:

```python
    context_limit_tokens: int = 8000
    input_price_per_million: float = 0.30
    output_price_per_million: float = 1.20
```

`.env.example` добавить:

```
CONTEXT_LIMIT_TOKENS=8000
INPUT_PRICE_PER_MILLION=0.30
OUTPUT_PRICE_PER_MILLION=1.20
```

`dependencies.py`:

```python
@lru_cache
def get_usage_config() -> UsageConfig:
    settings = get_settings()
    return UsageConfig(
        context_limit_tokens=settings.context_limit_tokens,
        input_price_per_million=settings.input_price_per_million,
        output_price_per_million=settings.output_price_per_million,
    )
```
`get_agent`: убрать временные `counter=TiktokenCounter(), config=UsageConfig()` и передавать `config=get_usage_config()`; экспортировать `get_usage_config` для routes.

- [ ] **Шаг 4. Schemas + routes + main**

`schemas.py`:

```python
class TokenUsageResponse(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


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


class DialogUsageResponse(BaseModel):
    history_tokens: int
    dialog_total_tokens: int
    dialog_cost_usd: float
    context_limit: int
    context_remaining: int
    warning: bool
```
`ChatResponse` + `usage: UsageResponse`. `ChatMessageResponse` + `usage: TokenUsageResponse | None = None`. `ChatDetailResponse` + `dialog_usage: DialogUsageResponse`.

`routes.py` — `send_message`: в `ChatResponse(...)` добавить `usage=_usage_response(result.usage)`. `get_chat`: собрать диалог и usage:

```python
@router.get("/api/chats/{chat_id}", response_model=ChatDetailResponse)
async def get_chat(
    chat_id: str,
    repository: Annotated[ChatRepository, Depends(get_repository)],
    counter: Annotated[TokenCounter, Depends(get_token_counter)],
    config: Annotated[UsageConfig, Depends(get_usage_config)],
) -> ChatDetailResponse:
    chat = await repository.get_chat(chat_id)
    dialog = build_dialog_usage(
        [ChatMessage(role="system", content=SYSTEM_PROMPT), *chat.messages],
        counter,
        config,
    )
    return ChatDetailResponse(
        **_summary_response(chat).model_dump(),
        messages=[
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
            for message in chat.messages
        ],
        dialog_usage=DialogUsageResponse(
            history_tokens=dialog.history_tokens,
            dialog_total_tokens=dialog.dialog_total_tokens,
            dialog_cost_usd=dialog.dialog_cost_usd,
            context_limit=dialog.context_limit,
            context_remaining=dialog.context_remaining,
            warning=dialog.warning,
        ),
    )
```
Хелперы в модуле:

```python
def _usage_response(report: UsageReport) -> UsageResponse:
    return UsageResponse(**vars(report))


def _dialog_response(dialog: DialogUsage) -> DialogUsageResponse:
    return DialogUsageResponse(**vars(dialog))
```

`main.py` — добавить хендлер (перед `ChatPersistenceError` не критично, порядок регистрации не важен):

```python
@app.exception_handler(ContextLimitExceeded)
async def context_limit_handler(request: Request, error: ContextLimitExceeded):
    return JSONResponse(
        status_code=413,
        content={
            "detail": (
                f"Диалог превысил лимит контекста ({error.estimated_tokens} из "
                f"{error.context_limit} токенов). Сообщение не отправлено и не сохранено. "
                "Начните новый чат."
            ),
            "estimated_tokens": error.estimated_tokens,
            "context_limit": error.context_limit,
        },
    )
```
(импорт `ContextLimitExceeded`).

- [ ] **Шаг 5. Прогнать весь бэкенд**

Run: `cd day8/backend && .venv/bin/pytest -q`
Ожидается: все PASS (~44).

- [ ] **Шаг 6. Закоммитить**

```bash
git add day8/backend && git commit -m "feat: expose token usage and context limit via api"
```

---

### Задача 8: Frontend — панель бюджета, строки usage, симуляция и баннер переполнения

**Файлы:**
- Создать: `day8/frontend/src/components/UsagePanel.jsx`
- Изменить: `day8/frontend/src/api.js`, `day8/frontend/src/App.jsx`, `day8/frontend/src/components/ChatPanel.jsx`, `day8/frontend/src/styles.css`

**Интерфейсы:**
- Consumes: API из задачи 7 (`usage` в POST messages, `dialog_usage`/`usage` в GET chat, HTTP 413)
- Produces: UI без изменения контрактов backend

- [ ] **Шаг 1. api.js — пробросить статус ошибки**

```js
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
```

- [ ] **Шаг 2. UsagePanel.jsx**

```jsx
export default function UsagePanel({ dialogUsage, message, simulating, onSimulate }) {
  const usage = message?.usage ?? dialogUsage;
  if (!usage) return null;

  const used = usage.context_limit - usage.context_remaining;
  const percent = Math.min(100, Math.round((used / usage.context_limit) * 100));
  const barClass = percent >= 100 ? 'danger' : usage.warning ? 'warning' : 'ok';

  return (
    <div className="usage-panel" aria-label="Бюджет контекста">
      <div className={`context-bar ${barClass}`} role="progressbar" aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100}>
        <div className="context-bar-fill" style={{ width: `${percent}%` }} />
      </div>
      <div className="usage-stats">
        <span title="Локальная оценка токенов до отправки">
          контекст ≈ {used} / {usage.context_limit} ({percent}%)
        </span>
        <span title="Точные токены из usage API, накопленные по диалогу">
          Σ токенов: {usage.dialog_total_tokens}
        </span>
        <span title="Оценка стоимости по worst-case ценам DeepSeek flash">
          ≈ ${usage.dialog_cost_usd.toFixed(5)}
        </span>
        <button
          className="simulate-button"
          disabled={simulating}
          onClick={onSimulate}
          type="button"
        >
          {simulating ? 'Симуляция…' : 'Симулировать длинный диалог'}
        </button>
      </div>
      {usage.warning && (
        <p className="usage-warning">
          Осталось меньше 20% бюджета контекста — скоро диалог упрётся в лимит.
        </p>
      )}
    </div>
  );
}
```
Примечание: у `message.usage` (UsageReport) есть `dialog_total_tokens`/`context_remaining`, у `dialog_usage` (GET) нет только `request_tokens` и т.п. — панель использует общие поля.

- [ ] **Шаг 3. ChatPanel.jsx — строка usage под ответом и баннер переполнения**

В props добавить `overflow`, `onDismissOverflow`. В разметке: над `error`-карточкой/внутри conversation вывести баннер, а после списка сообщений — строку под assistant-сообщениями с usage:

```jsx
{overflow && (
  <div className="overflow-banner">
    <span>{overflow}</span>
    <button type="button" onClick={onDismissOverflow}>Понятно</button>
  </div>
)}
```
и внутри map по messages для assistant с `item.usage`:

```jsx
{item.role === 'assistant' && item.usage && (
  <div className="usage-line">
    ответ {item.usage.completion_tokens} · промпт {item.usage.prompt_tokens} · всего {item.usage.total_tokens} токенов
  </div>
)}
```
(живой ответ из POST содержит `usage.response_tokens/prompt_tokens_api/total_tokens_api` — App нормализует их в поле `usage` сообщения в один вид `{prompt_tokens, completion_tokens, total_tokens}`, см. шаг 4.)

- [ ] **Шаг 4. App.jsx — состояние usage, симуляция, нормализация**

Добавить state: `dialogUsage`, `overflow`, `simulating`. `loadChat` после `getChat` делать `setDialogUsage(chat.dialog_usage)` и `setMessages(chat.messages.map(...))` (usage уже по запросу, ключи совпадают). Извлечь `submitMessage(text)`:

```jsx
async function submitMessage(text, { isSimulated = false } = {}) {
  setLoading(true);
  setError('');
  setResult(null);
  if (!isSimulated) setOverflow('');
  setStages([
    { name: 'UI', status: 'completed' },
    { name: 'Agent', status: 'active' },
    { name: 'DeepSeek API', status: 'pending' },
  ]);
  try {
    const response = await sendMessage(selectedChatId, text);
    setMessages(current => [
      ...current,
      { role: 'user', content: text },
      {
        role: 'assistant',
        content: response.answer,
        usage: {
          prompt_tokens: response.usage.prompt_tokens_api,
          completion_tokens: response.usage.response_tokens,
          total_tokens: response.usage.total_tokens_api,
        },
      },
    ]);
    setResult(response);
    setStages(response.stages);
    setDialogUsage(response.usage);
    setChats(await listChats());
    return true;
  } catch (requestError) {
    setStages(currentStages => currentStages.map(stage => ({
      ...stage,
      status: stage.name === 'DeepSeek API' ? 'error' : stage.status,
    })));
    if (requestError.status === 413) {
      setOverflow(requestError.message);
      const chat = await getChat(selectedChatId);
      setDialogUsage(chat.dialog_usage);
      return false;
    }
    setError(requestError.message);
    return false;
  } finally {
    setLoading(false);
  }
}
```
`handleSubmit` → `await submitMessage(trimmedMessage)`. Симуляция:

```jsx
const SIMULATION_FILLER = 'Подробно опиши, как устроен бюджет контекста языковой модели, зачем считать токены запроса, истории и ответа, и как это влияет на стоимость диалога. ';

async function handleSimulate() {
  if (!selectedChatId || loading || simulating) return;
  setSimulating(true);
  for (let part = 1; part <= 12; part += 1) {
    const ok = await submitMessage(`Часть ${part}. ${SIMULATION_FILLER.repeat(40)}`, { isSimulated: true });
    if (!ok) break;
  }
  setSimulating(false);
}
```
`handleDeleteChat`/`handleCreateChat` сбрасывать `setDialogUsage(null); setOverflow('')`. В JSX вставить `<UsagePanel dialogUsage={dialogUsage} message={result} simulating={simulating} onSimulate={handleSimulate} />` в `ChatPanel` перед conversation (props пробросить: `overflow`, `onDismissOverflow={() => setOverflow('')}`, `simulating`, `onSimulate`). При `overflow !== ''` блокировать composer: `disabled={loading || initializing || simulating || Boolean(overflow)}`.

Hero-тексты: `DAY 08 / TOKEN COUNTING`; заголовок `<h1>Диалог, который<br /><em>виден в токенах.</em></h1>`; подзаголовок: «Локальная оценка до отправки, точный usage DeepSeek после — и лимит контекста, который однажды заканчивается.» Footer: `TOKEN BUDGET`.

- [ ] **Шаг 5. styles.css — добавить классы**

```css
.usage-panel { display: grid; gap: 8px; padding: 10px 12px; border: 1px solid #285148; border-radius: 12px; background: #101d1c; margin-bottom: 12px; }
.context-bar { height: 8px; border-radius: 999px; background: #1b2f2e; overflow: hidden; }
.context-bar-fill { height: 100%; border-radius: 999px; background: #35d0a5; transition: width .4s ease; }
.context-bar.warning .context-bar-fill { background: #f0b429; }
.context-bar.danger .context-bar-fill { background: #ff7a59; }
.usage-stats { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 14px; color: #829397; font-size: 12.5px; }
.usage-warning { margin: 0; color: #f0b429; font-size: 12.5px; }
.simulate-button { margin-left: auto; padding: 6px 12px; border: 1px solid #285148; border-radius: 999px; color: #dffaf5; background: transparent; cursor: pointer; font-size: 12.5px; }
.simulate-button:hover:not(:disabled) { background: #132522; }
.simulate-button:disabled { cursor: not-allowed; opacity: .65; }
.usage-line { margin: -6px 0 8px auto; width: fit-content; color: #6c8085; font-size: 11.5px; }
.overflow-banner { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 10px; padding: 10px 12px; border: 1px solid #6b3a2e; border-radius: 10px; background: #241511; color: #ffd8c8; font-size: 13px; }
.overflow-banner button { border: 1px solid #6b3a2e; border-radius: 8px; padding: 4px 10px; color: #ffd8c8; background: transparent; cursor: pointer; }
```

- [ ] **Шаг 6. Сборка**

Run: `cd day8/frontend && npm run build`
Ожидается: успешно, exit 0.

- [ ] **Шаг 7. Закоммитить**

```bash
git add day8/frontend && git commit -m "feat: show token budget panel and overflow flow in ui"
```

---

### Задача 9: Ручная проверка трёх сценариев и README

**Файлы:**
- Создать/изменить: `day8/README.md`, `README.md` (корневой)

**Интерфейсы:**
- Consumes: готовое приложение; реальный DeepSeek-ключ в `day8/backend/.env`
- Produces: задокументированный день + фактические числа сценариев

- [ ] **Шаг 1. Поднять приложение**

Остановить процессы day7 на 8000/5173 (сообщить пользователю), затем:

```bash
cd day8/backend && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
cd day8/frontend && npm run dev
```
(в фоне, логи в `/tmp/day8-backend.log`, `/tmp/day8-frontend.log`)

- [ ] **Шаг 2. Сценарий A — короткий диалог (2–3 реплики)**

Через API (curl: POST /api/chats, затем 2 сообщения) либо UI. Зафиксировать фактические числа из `usage` ответов в таблицу README: request/history/response-оценки, API usage, `dialog_cost_usd`.

- [ ] **Шаг 3. Сценарий B — длинный диалог**

Кнопка «Симулировать длинный диалог» в UI (или curl-цикл теми же сообщениями). Остановиться на warning ≥80%, не дожидаясь 413. Зафиксировать, как растут `history_tokens` (линейно) и `prompt_tokens_api` (растёт быстрее реплик), и накопленную стоимость.

- [ ] **Шаг 4. Сценарий C — переполнение**

Продолжить симуляцию до HTTP 413. Проверить: 413 содержит `estimated_tokens`/`context_limit`; сообщение НЕ появилось в `GET /api/chats/{id}`; composer заблокирован с баннером; новый чат (`CONTEXT_LIMIT_TOKENS` не меняя) работает. Записать фактические числа.

- [ ] **Шаг 5. `day8/README.md`**

Полностью переписать: цель дня (зачем считать токены — история пересылается каждый раз, платим за неё повторно), архитектура (два источника чисел: оценка tiktoken vs usage API), таблицы трёх сценариев с ФАКТИЧЕСКИМИ числами из шагов 2–4, разделы: запуск (`cp .env.example .env`, venv, uvicorn, npm, `CONTEXT_LIMIT_TOKENS`), эндпоинты (добавить 413), «что ломается при переполнении» (сообщение не сохраняется, диалог продолжаться не может, нужно начать новый чат), реальные факты DeepSeek: `deepseek-chat` сейчас обслуживается моделью `deepseek-flash` (V4.1-Flash), реальный лимит контекста — 1M токенов, реальная ошибка API — HTTP 400 `context_length_exceeded` (мы её тоже маппим в 413), цены worst-case пик taken из официальной доки; почему демо-бюджет 8000. Ограничения: локальные числа — оценка; автообрезка истории отсутствует (out of scope).

- [ ] **Шаг 6. Корневой `README.md`**

В список дней добавить строки (день 7 отсутствует — добавить и его):

```markdown
- [`day7`](./day7) — сохранение контекста: история чатов в JSON переживает перезапуск.
- [`day8`](./day8) — подсчёт токенов и лимит контекста: оценка запроса/истории/ответа, накопительная стоимость и переполнение бюджета.
```

- [ ] **Шаг 7. Итоговая верификация**

```bash
cd day8/backend && .venv/bin/pytest -q
cd day8/frontend && npm run build
git diff --check
git diff --exit-code -- day6 day7
git check-ignore -q day8/backend/.env
```
Ожидается: все тесты PASS, build успешен, `day6`/`day7` без изменений, `.env` ignored.

- [ ] **Шаг 8. Закоммитить**

```bash
git add day8 README.md && git commit -m "docs: document day8 token counting with live scenarios"
```
