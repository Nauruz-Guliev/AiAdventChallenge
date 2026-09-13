from dataclasses import dataclass
from typing import Literal


StageStatus = Literal["pending", "active", "completed", "error"]


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["system", "user", "assistant"]
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


class InvalidUserMessage(ValueError):
    pass


class ChatNotFound(RuntimeError):
    pass


class ChatPersistenceError(RuntimeError):
    pass


class LLMGatewayError(RuntimeError):
    pass


class AuthenticationGatewayError(LLMGatewayError):
    pass


class RateLimitGatewayError(LLMGatewayError):
    pass


class GatewayTimeoutError(LLMGatewayError):
    pass
