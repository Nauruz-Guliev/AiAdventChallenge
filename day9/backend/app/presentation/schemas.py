from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.domain.models import StageStatus


class ChatMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    compress: bool = True

    @field_validator("message")
    @classmethod
    def message_cannot_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message cannot be blank")
        return value


class StageResponse(BaseModel):
    name: str
    status: StageStatus


class CompressionResponse(BaseModel):
    applied: bool
    before_tokens: int
    after_tokens: int
    saved_tokens: int
    saved_percent: int
    summarization_tokens: int
    summarization_cost_usd: float


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
    compression: CompressionResponse | None = None


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


class ChatDetailResponse(ChatSummaryResponse):
    messages: list[ChatMessageResponse]
    dialog_usage: DialogUsageResponse
    summary: str | None = None
    summary_covers: int = 0
