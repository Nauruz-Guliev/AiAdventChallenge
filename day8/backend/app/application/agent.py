from time import perf_counter

from app.application.ports.chat_repository import ChatRepository
from app.application.ports.llm_gateway import LLMGateway
from app.application.ports.token_counter import TokenCounter
from app.application.usage import build_dialog_usage
from app.domain.models import (
    AgentResult,
    AgentStage,
    ChatMessage,
    ContextLimitExceeded,
    InvalidUserMessage,
    UsageConfig,
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
        counter: TokenCounter,
        config: UsageConfig,
        model: str = "deepseek-chat",
    ):
        self._gateway = gateway
        self._repository = repository
        self._counter = counter
        self._config = config
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

        system_message = ChatMessage(role="system", content=SYSTEM_PROMPT)
        history_messages = [system_message, *chat.messages]
        new_message = ChatMessage(role="user", content=message)
        history_tokens = self._counter.count_messages(history_messages)
        request_tokens = self._counter.count_messages([new_message])
        estimated = history_tokens + request_tokens
        if estimated > self._config.context_limit_tokens:
            raise ContextLimitExceeded(
                estimated, self._config.context_limit_tokens
            )

        started_at = perf_counter()
        response = await self._gateway.complete([*history_messages, new_message])
        answer = response.text.strip()
        updated_chat = await self._repository.append_exchange(
            chat_id, message, answer, response.usage
        )

        dialog = build_dialog_usage(
            [system_message, *updated_chat.messages],
            self._counter,
            self._config,
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
                request_tokens=request_tokens,
                history_tokens=history_tokens,
                response_tokens=response.usage.completion_tokens,
                prompt_tokens_api=response.usage.prompt_tokens,
                completion_tokens_api=response.usage.completion_tokens,
                total_tokens_api=response.usage.total_tokens,
                dialog_total_tokens=dialog.dialog_total_tokens,
                dialog_cost_usd=dialog.dialog_cost_usd,
                context_limit=dialog.context_limit,
                context_remaining=dialog.context_remaining,
                warning=dialog.warning,
            ),
        )
