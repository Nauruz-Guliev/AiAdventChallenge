from typing import Protocol

from app.domain.models import ChatMessage


class TokenCounter(Protocol):
    def count_text(self, text: str) -> int: ...

    def count_messages(self, messages: list[ChatMessage]) -> int: ...
