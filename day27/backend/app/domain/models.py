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
    images: list[str] | None = None

    def to_ollama(self) -> dict:
        msg: dict = {"role": self.role.value, "content": self.content}
        if self.images:
            msg["images"] = list(self.images)
        return msg

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


@dataclass
class PhotoInput:
    data: bytes
    mime: str = "image/jpeg"
    caption: str | None = None


@dataclass
class ChatState:
    chat_id: int
    system_prompt: str
    model: str
    messages: list[ChatMessage] = field(default_factory=list)
    show_thinking: bool = False
    updated_at: str = ""

    def history(self) -> list[ChatMessage]:
        return [m for m in self.messages if m.role != Role.SYSTEM]

    def to_dict(self) -> dict:
        return {
            "chat_id": self.chat_id,
            "system_prompt": self.system_prompt,
            "model": self.model,
            "show_thinking": self.show_thinking,
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
            show_thinking=bool(d.get("show_thinking", False)),
            updated_at=d.get("updated_at", ""),
        )
