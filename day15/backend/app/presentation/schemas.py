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
    profile_tokens: int = 0


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


class UsedWorkingMemoryResponse(BaseModel):
    goal: str
    constraints: list[str]
    decisions: list[str]


class UsedProfileResponse(BaseModel):
    title: str
    name: str
    role: str
    language: str
    tone: str
    length: str
    structure: str
    constraints: list[str]


class UsedMemoryResponse(BaseModel):
    history_count: int
    profile: UsedProfileResponse | None = None
    working: UsedWorkingMemoryResponse | None = None
    long_term: dict[str, list[str]] = {}


class TransitionRejectionResponse(BaseModel):
    event: str
    from_stage: str
    to_stage: str
    reason: str


class TaskStateResponse(BaseModel):
    active: bool = False
    task: str | None = None
    stage: str | None = None
    stage_index: int = 0
    step: int = 0
    total_steps: int = 0
    step_label: str | None = None
    expected_action: str
    paused: bool = False
    steps: list[str] = []
    allowed_stages: list[str] = []
    rejections: list[TransitionRejectionResponse] = []


class TransitionRequest(BaseModel):
    event: str = Field(min_length=1, max_length=64)


class StageOptionResponse(BaseModel):
    key: str
    label: str


class EventOptionResponse(BaseModel):
    event: str
    label: str
    stage: str


class TransitionInfoResponse(BaseModel):
    stage: str
    label: str
    allowed: list[str]


class TransitionsResponse(BaseModel):
    stages: list[StageOptionResponse]
    events: list[EventOptionResponse]
    transitions: list[TransitionInfoResponse]


class InvariantResponse(BaseModel):
    id: str
    text: str
    category: str
    category_label: str


class InvariantCreateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    category: Literal["architecture", "decision", "stack", "business"]

    @field_validator("text")
    @classmethod
    def text_cannot_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Invariant text cannot be blank")
        return value


class ViolationResponse(BaseModel):
    invariant_id: str
    reason: str
    invariant: InvariantResponse | None = None


class ChatResponse(BaseModel):
    chat_id: str
    answer: str
    model: str
    duration_ms: int
    stages: list[StageResponse]
    usage: UsageResponse
    used: UsedMemoryResponse | None = None
    task: TaskStateResponse | None = None
    violation: ViolationResponse | None = None


class TokenUsageResponse(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatMessageResponse(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    usage: TokenUsageResponse | None = None
    used: UsedMemoryResponse | None = None


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


class CandidateApproveRequest(BaseModel):
    text: str | None = None
    category: str | None = None


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


class ProfileResponse(BaseModel):
    id: str
    title: str
    name: str
    role: str
    language: str
    tone: Literal["formal", "friendly", "neutral"]
    length: Literal["short", "medium", "detailed"]
    structure: Literal["prose", "bullets", "markdown"]
    constraints: list[str]


class ProfileStoreResponse(BaseModel):
    active_id: str
    profiles: list[ProfileResponse]


class ProfileCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=60)
    name: str = ""
    role: str = ""
    language: str = "ru"
    tone: Literal["formal", "friendly", "neutral"] = "neutral"
    length: Literal["short", "medium", "detailed"] = "medium"
    structure: Literal["prose", "bullets", "markdown"] = "prose"
    constraints: list[str] = []


class ProfileUpdateRequest(BaseModel):
    title: str | None = None
    name: str | None = None
    role: str | None = None
    language: str | None = None
    tone: Literal["formal", "friendly", "neutral"] | None = None
    length: Literal["short", "medium", "detailed"] | None = None
    structure: Literal["prose", "bullets", "markdown"] | None = None
    constraints: list[str] | None = None


class ProfilePresetResponse(BaseModel):
    key: str
    label: str
    tone: str
    length: str
    structure: str
    constraints: list[str]


class ProfileFromPresetRequest(BaseModel):
    key: str