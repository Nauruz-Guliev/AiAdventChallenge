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
