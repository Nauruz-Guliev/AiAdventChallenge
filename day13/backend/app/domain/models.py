from dataclasses import dataclass, field
from typing import Literal


StageStatus = Literal["pending", "active", "completed", "error"]
WorkingStatus = Literal["active", "done"]
CandidateStatus = Literal["pending", "approved", "rejected"]

LONG_TERM_CATEGORIES = ("profile", "decisions", "knowledge")

PROFILE_TONES = ("formal", "friendly", "neutral")
PROFILE_LENGTHS = ("short", "medium", "detailed")
PROFILE_STRUCTURES = ("prose", "bullets", "markdown")
DEFAULT_ACTIVE_PRESET_KEY = "business"


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
    profile_max_constraints: int = 20
    profile_max_item_chars: int = 300


@dataclass(frozen=True)
class MemoryInfo:
    long_term_count: int
    long_term_tokens: int
    working_tokens: int
    history_tokens: int
    candidate_tokens: int
    profile_tokens: int = 0


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
    used: dict | None = None


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
    used: dict | None = None


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
class UserProfile:
    id: str
    title: str = ""
    name: str = ""
    role: str = ""
    language: str = "ru"
    tone: str = "neutral"
    length: str = "medium"
    structure: str = "prose"
    constraints: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return (
            not self.name.strip()
            and not self.role.strip()
            and self.language == "ru"
            and self.tone == "neutral"
            and self.length == "medium"
            and self.structure == "prose"
            and not self.constraints
        )


@dataclass
class ProfileStore:
    active_id: str = ""
    profiles: list[UserProfile] = field(default_factory=list)

    def find(self, profile_id: str) -> UserProfile | None:
        for profile in self.profiles:
            if profile.id == profile_id:
                return profile
        return None

    def active(self) -> UserProfile | None:
        return self.find(self.active_id)


@dataclass(frozen=True)
class ProfilePreset:
    key: str
    label: str
    tone: str
    length: str
    structure: str
    constraints: tuple[str, ...]


PROFILE_PRESETS = (
    ProfilePreset(
        "neutral",
        "Нейтральный (без персонализации)",
        "neutral",
        "medium",
        "prose",
        (),
    ),
    ProfilePreset(
        "business",
        "Деловой",
        "formal",
        "medium",
        "markdown",
        ("без эмодзи", "без воды"),
    ),
    ProfilePreset(
        "concise",
        "Коротко и по делу",
        "neutral",
        "short",
        "bullets",
        ("без вступлений и итогов", "не больше трёх пунктов"),
    ),
    ProfilePreset(
        "mentor",
        "Наставник",
        "friendly",
        "detailed",
        "markdown",
        ("объясняй термины простыми словами", "приводи пример"),
    ),
)


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


class ProfileNotFound(RuntimeError):
    pass


class ProfileConflict(ValueError):
    pass