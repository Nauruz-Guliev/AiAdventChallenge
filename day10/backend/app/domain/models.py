from dataclasses import dataclass, field
from typing import Literal


StageStatus = Literal["pending", "active", "completed", "error"]


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
    sliding_window_messages: int = 10
    facts_max_items: int = 20


@dataclass(frozen=True)
class ContextInfo:
    mode: str
    sent_messages: int
    total_messages: int
    facts_count: int
    fact_update_tokens: int
    fact_update_cost_usd: float


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
    context: ContextInfo | None = None


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
    mode: str = "sliding"

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


class InvalidUserMessage(ValueError):
    pass


class ChatNotFound(RuntimeError):
    pass


class BranchNotFound(RuntimeError):
    pass


class LastBranchError(ValueError):
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


class ContextLimitExceeded(RuntimeError):
    def __init__(self, estimated_tokens: int = 0, context_limit: int = 0):
        super().__init__(
            f"Context limit exceeded: {estimated_tokens}/{context_limit}"
        )
        self.estimated_tokens = estimated_tokens
        self.context_limit = context_limit
