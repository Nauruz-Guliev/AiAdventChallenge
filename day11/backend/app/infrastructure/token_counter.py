import tiktoken

from app.domain.models import ChatMessage

PER_MESSAGE_OVERHEAD_TOKENS = 4


class TiktokenCounter:
    """Локальная оценка токенов.

    У DeepSeek собственный токенизатор, cl100k_base даёт приближение,
    поэтому все числа из этого класса — оценка, а не биллинг.
    """

    def __init__(self, encoding_name: str = "cl100k_base"):
        self._encoding = tiktoken.get_encoding(encoding_name)

    def count_text(self, text: str) -> int:
        return len(self._encoding.encode(text))

    def count_messages(self, messages: list[ChatMessage]) -> int:
        return sum(
            self.count_text(message.content) + PER_MESSAGE_OVERHEAD_TOKENS
            for message in messages
        )
