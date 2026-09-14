from time import perf_counter

from app.application.ports.chat_repository import ChatRepository
from app.application.ports.llm_gateway import LLMGateway
from app.application.ports.token_counter import TokenCounter
from app.application.context_strategy import (
    assemble_history,
    build_facts_update_messages,
    parse_facts_update,
)
from app.application.usage import build_dialog_usage, exchange_cost_usd
from app.domain.models import (
    ContextInfo,
    AgentResult,
    AgentStage,
    ChatMessage,
    ContextLimitExceeded,
    InvalidUserMessage,
    TokenUsage,
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

    async def run(
        self, chat_id: str, user_text: str, mode: str = "sliding"
    ) -> AgentResult:
        message = self._validate_message(user_text)
        chat = await self._repository.get_chat(chat_id)
        branch = chat.active_branch
        new_message = ChatMessage(role="user", content=message)
        system_message = ChatMessage(role="system", content=SYSTEM_PROMPT)

        fact_update_tokens = 0
        fact_update_cost = 0.0
        facts_count = len(branch.facts)
        if mode == "facts":
            extraction = await self._gateway.complete(
                build_facts_update_messages(
                    branch.facts, message, self._config.facts_max_items
                )
            )
            updated_facts = parse_facts_update(
                extraction.text, self._config.facts_max_items
            )
            if updated_facts is not None:
                await self._repository.save_facts(chat_id, branch.id, updated_facts)
                facts_count = len(updated_facts)
            fact_update_tokens = extraction.usage.total_tokens
            fact_update_cost = round(
                exchange_cost_usd(extraction.usage, self._config), 6
            )

        total_messages = len(branch.messages)
        assembled = assemble_history(mode, branch, new_message, self._config)
        context = [system_message, *assembled]
        request_tokens = self._counter.count_messages([new_message])
        sent_history_tokens = (
            self._counter.count_messages(context) - request_tokens
        )
        estimated = sent_history_tokens + request_tokens
        if estimated > self._config.context_limit_tokens:
            raise ContextLimitExceeded(
                estimated, self._config.context_limit_tokens
            )
        sent_messages = (
            len(branch.messages)
            if mode in ("full", "branching")
            else min(self._config.sliding_window_messages, len(branch.messages))
        )

        started_at = perf_counter()
        response = await self._gateway.complete(context)
        answer = response.text.strip()
        updated_chat = await self._repository.append_exchange(
            chat_id,
            message,
            answer,
            response.usage,
            branch_id=branch.id,
            mode=mode,
        )

        dialog = build_dialog_usage(
            [system_message, *updated_chat.messages], self._counter, self._config
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
                history_tokens=sent_history_tokens,
                response_tokens=response.usage.completion_tokens,
                prompt_tokens_api=response.usage.prompt_tokens,
                completion_tokens_api=response.usage.completion_tokens,
                total_tokens_api=response.usage.total_tokens,
                dialog_total_tokens=dialog.dialog_total_tokens,
                dialog_cost_usd=dialog.dialog_cost_usd,
                context_limit=dialog.context_limit,
                context_remaining=dialog.context_remaining,
                warning=dialog.warning,
                context=ContextInfo(
                    mode=mode,
                    sent_messages=sent_messages,
                    total_messages=total_messages,
                    facts_count=facts_count,
                    fact_update_tokens=fact_update_tokens,
                    fact_update_cost_usd=fact_update_cost,
                ),
            ),
        )
