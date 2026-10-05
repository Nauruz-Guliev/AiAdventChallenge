from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _as_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(x).strip() for x in value if str(x).strip()]


@dataclass
class TaskMemory:
    goal: str = ""
    clarifications: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    terms: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "goal": self.goal,
            "clarifications": list(self.clarifications),
            "constraints": list(self.constraints),
            "terms": list(self.terms),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TaskMemory":
        return cls(
            goal=(data.get("goal") or "").strip(),
            clarifications=_as_list(data.get("clarifications")),
            constraints=_as_list(data.get("constraints")),
            terms=_as_list(data.get("terms")),
        )


@dataclass
class Message:
    role: str
    text: str
    at: str = field(default_factory=_now)
    sources: list[Hit] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "text": self.text,
            "at": self.at,
            "sources": [
                {
                    "chunk_id": h.chunk_id,
                    "source": h.source,
                    "title": h.title,
                    "section": h.section,
                    "score": h.score,
                    "text": h.text,
                }
                for h in self.sources
            ],
            "citations": [
                {
                    "ref": c.ref,
                    "chunk_id": c.chunk_id,
                    "source": c.source,
                    "section": c.section,
                    "quote": c.quote,
                    "grounded": c.grounded,
                }
                for c in self.citations
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        return cls(
            role=data["role"],
            text=data["text"],
            at=data.get("at", _now()),
            sources=[Hit(**s) for s in data.get("sources", [])],
            citations=[Citation(**c) for c in data.get("citations", [])],
        )


@dataclass
class Session:
    id: str
    created_at: str = field(default_factory=_now)
    memory: TaskMemory = field(default_factory=TaskMemory)
    messages: list[Message] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "memory": self.memory.to_dict(),
            "messages": [m.to_dict() for m in self.messages],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        return cls(
            id=data["id"],
            created_at=data.get("created_at", _now()),
            memory=TaskMemory.from_dict(data.get("memory", {})),
            messages=[Message.from_dict(m) for m in data.get("messages", [])],
        )


@dataclass(frozen=True)
class ChatTurn:
    reply: str
    sources: tuple[Hit, ...]
    citations: tuple[Citation, ...]
    memory: TaskMemory
    answerable: bool = True
    relevance: float | None = None


@dataclass
class ScenarioReport:
    name: str
    turns: int
    all_with_sources: bool
    goal_kept: bool
    memory_grown: bool
    passed: bool
    final_memory: dict

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "turns": self.turns,
            "all_with_sources": self.all_with_sources,
            "goal_kept": self.goal_kept,
            "memory_grown": self.memory_grown,
            "passed": self.passed,
            "final_memory": self.final_memory,
        }


class LLMGatewayError(RuntimeError):
    pass


class IndexNotFound(RuntimeError):
    pass


class InvalidQuestion(ValueError):
    pass


class SessionNotFound(KeyError):
    pass
