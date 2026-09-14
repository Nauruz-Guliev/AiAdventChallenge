from time import perf_counter

from app.application.ports.chat_repository import ChatRepository
from app.application.ports.llm_gateway import LLMGateway
from app.domain.models import (
    AgentResult,
    AgentStage,
    ChatMessage,
    InvalidUserMessage,
    UsageReport,
)


SYSTEM_PROMPT = (
    "You are a helpful assistant. Answer in the same language as the user. "
    "Be concise, clear, and complete. Never reveal private hidden chain-of-thought; "
    "give a short useful summary instead if the user asks how you reasoned."
)
MAX_MESSAGE_LENGTH = 4000


class Agent:
    def __init__(
        self,
        gateway: LLMGateway,
        repository: ChatRepository,
        model: str = "deepseek-chat",
    ):
        self._gateway = gateway
        self._repository = repository
        self._model = model

    @staticmethod
    def _validate_message(user_text: str) -> str:
        if not isinstance(user_text, str):
            raise InvalidUserMessage("Message must be a string")
        message = user_text.strip()
        if not message:
            raise InvalidUserMessage("Message cannot be blank")
        if len(message) > MAX_MESSAGE_LENGTH:
            raise InvalidUserMessage(
                f"Message must be shorter than {MAX_MESSAGE_LENGTH} characters"
            )
        return message

    async def run(self, chat_id: str, user_text: str) -> AgentResult:
        message = self._validate_message(user_text)
        chat = await self._repository.get_chat(chat_id)
        messages = [ChatMessage(role="system", content=SYSTEM_PROMPT)]
        messages.extend(chat.messages)
        messages.append(ChatMessage(role="user", content=message))

        started_at = perf_counter()
        response = await self._gateway.complete(messages)
        answer = response.text.strip()
        await self._repository.append_exchange(
            chat_id, message, answer, response.usage
        )

        return AgentResult(
            answer=answer,
            model=response.model or self._model,
            duration_ms=round((perf_counter() - started_at) * 1000),
            stages=[
                AgentStage(name="UI", status="completed"),
                AgentStage(name="Agent", status="completed"),
                AgentStage(name="DeepSeek API", status="completed"),
            ],
            usage=UsageReport(
                request_tokens=0,
                history_tokens=0,
                response_tokens=response.usage.completion_tokens,
                prompt_tokens_api=response.usage.prompt_tokens,
                completion_tokens_api=response.usage.completion_tokens,
                total_tokens_api=response.usage.total_tokens,
                dialog_total_tokens=response.usage.total_tokens,
                dialog_cost_usd=0.0,
                context_limit=0,
                context_remaining=0,
                warning=False,
            ),
        )
