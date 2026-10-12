from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class ChatMessage:
    role: Role
    content: str

    def to_ollama(self) -> dict:
        return {"role": self.role.value, "content": self.content}

    def to_dict(self) -> dict:
        return {"role": self.role.value, "content": self.content}

    @classmethod
    def from_dict(cls, d: dict) -> "ChatMessage":
        return cls(role=Role(d["role"]), content=d.get("content", ""))


@dataclass
class GenerationStats:
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    eval_duration_ns: int = 0
    total_duration_ns: int = 0

    @property
    def tokens_per_second(self) -> float:
        if not self.eval_duration_ns or not self.completion_tokens:
            return 0.0
        return self.completion_tokens / (self.eval_duration_ns / 1e9)


@dataclass(frozen=True)
class Hit:
    chunk_id: str
    source: str
    title: str
    section: str
    score: float
    text: str


@dataclass(frozen=True)
class Citation:
    ref: int
    chunk_id: str
    source: str
    section: str
    quote: str
    grounded: bool


@dataclass(frozen=True)
class RagAnswer:
    reply: str
    sources: tuple[Hit, ...] = ()
    citations: tuple[Citation, ...] = ()
    answerable: bool = True
    relevance: float | None = None
    stats: GenerationStats | None = None


@dataclass
class ChatState:
    chat_id: int
    system_prompt: str
    model: str
    messages: list[ChatMessage] = field(default_factory=list)
    rag_enabled: bool = True
    think: bool = False
    last_question: str = ""
    updated_at: str = ""

    def history(self) -> list[ChatMessage]:
        return [m for m in self.messages if m.role != Role.SYSTEM]

    def to_dict(self) -> dict:
        return {
            "chat_id": self.chat_id,
            "system_prompt": self.system_prompt,
            "model": self.model,
            "rag_enabled": self.rag_enabled,
            "think": self.think,
            "last_question": self.last_question,
            "updated_at": self.updated_at,
            "messages": [m.to_dict() for m in self.messages],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ChatState":
        msgs = [
            m
            for m in (ChatMessage.from_dict(x) for x in d.get("messages", []))
            if m.role != Role.SYSTEM
        ]
        return cls(
            chat_id=int(d["chat_id"]),
            system_prompt=d.get("system_prompt", ""),
            model=d.get("model", ""),
            messages=msgs,
            rag_enabled=bool(d.get("rag_enabled", True)),
            think=bool(d.get("think", False)),
            last_question=d.get("last_question", ""),
            updated_at=d.get("updated_at", ""),
        )


@dataclass(frozen=True)
class EvalQuestion:
    id: str
    question: str
    expectation: str
    sources: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvalRow:
    label: str
    quality_mean: float
    quality_std: float
    latency_mean_ms: float
    latency_std_ms: float
    tokens_per_second: float
    error_rate: float
    runs: int


@dataclass(frozen=True)
class EvalReport:
    rows: tuple[EvalRow, ...]
    questions: int
    runs: int


class OllamaUnavailable(RuntimeError):
    pass


class CloudUnavailable(RuntimeError):
    pass


class IndexNotFound(RuntimeError):
    pass


class InvalidQuestion(ValueError):
    pass
