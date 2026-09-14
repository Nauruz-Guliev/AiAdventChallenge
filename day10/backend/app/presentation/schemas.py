from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.domain.models import StageStatus


ContextMode = Literal["full", "sliding", "facts", "branching"]


class ChatMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    mode: ContextMode = "sliding"

    @field_validator("message")
    @classmethod
    def message_cannot_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message cannot be blank")
        return value


class StageResponse(BaseModel):
    name: str
    status: StageStatus


class ContextResponse(BaseModel):
    mode: str
    sent_messages: int
    total_messages: int
    facts_count: int
    fact_update_tokens: int
    fact_update_cost_usd: float


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
    context: ContextResponse | None = None


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


class BranchResponse(BaseModel):
    id: str
    name: str
    fork_at: int | None
    facts: dict[str, str]
    messages: list[ChatMessageResponse]


class BranchCreateRequest(BaseModel):
    after_message_index: int = Field(ge=0)
    name: str = Field(min_length=1, max_length=40)


class ActiveBranchRequest(BaseModel):
    branch_id: str


class FactsUpdateRequest(BaseModel):
    facts: dict[str, str]


class ChatDetailResponse(ChatSummaryResponse):
    messages: list[ChatMessageResponse]
    branches: list[BranchResponse] = []
    active_branch_id: str | None = None
    mode: str = "sliding"
    dialog_usage: DialogUsageResponse


class CompareModeResponse(BaseModel):
    mode: str
    chat_id: str
    survived: dict[str, bool]
    prompt_tokens: int
    completion_tokens: int
    fact_update_tokens: int
    calls: int
    duration_ms: int
    error: str | None = None
