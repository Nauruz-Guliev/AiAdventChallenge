from time import perf_counter

from app.application.memory import (
    build_candidate_messages,
    build_long_term_block,
    build_memory_trace,
    build_prompt,
    build_working_block,
    parse_candidates,
    parse_command_category,
    parse_memory_command,
)
from app.application.ports.chat_repository import ChatRepository
from app.application.ports.llm_gateway import LLMGateway
from app.application.ports.profile_repository import ProfileRepository
from app.application.ports.token_counter import TokenCounter
from app.application.profiles import build_profile_block
from app.application.usage import build_dialog_usage, exchange_cost_usd
from app.domain.models import (
    AgentResult,
    AgentStage,
    CandidateConflict,
    ChatMessage,
    ContextLimitExceeded,
    InvalidUserMessage,
    MemoryInfo,
    UsageConfig,
    UsageReport,
    UserProfile,
)


SYSTEM_PROMPT = (
    "You are a helpful assistant. Answer in the same language as the user. "
    "Be concise, clear, and complete. Never reveal private hidden chain-of-thought; "
    "give a short useful summary instead if the user asks how you reasoned."
)
MAX_MESSAGE_LENGTH = 4000
CANDIDATE_LIMIT = 5


class Agent:
    def __init__(
        self,
        gateway: LLMGateway,
        repository: ChatRepository,
        counter: TokenCounter,
        config: UsageConfig,
        model: str = "deepseek-chat",
        candidates_enabled: bool = True,
        profiles: ProfileRepository | None = None,
    ):
        self._gateway = gateway
        self._repository = repository
        self._counter = counter
        self._config = config
        self._model = model
        self._candidates_enabled = candidates_enabled
        self._profiles = profiles

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
        long_term = await self._repository.get_long_term()

        profile: UserProfile | None = None
        if self._profiles is not None:
            profile = await self._profiles.get_active()

        command_text = parse_memory_command(message)
        command_tokens = 0
        if command_text is not None:
            if not command_text:
                raise InvalidUserMessage("Memory command is empty")
            classification = await self._gateway.complete(
                build_candidate_messages(command_text, "", long_term, 1)
            )
            command_tokens = classification.usage.total_tokens
            category = parse_command_category(classification.text)
            try:
                await self._repository.add_long_term_entry(
                    category, command_text, chat_id
                )
            except CandidateConflict:
                pass
            long_term = await self._repository.get_long_term()

        new_message = ChatMessage(role="user", content=message)
        prompt = build_prompt(chat, long_term, SYSTEM_PROMPT, profile=profile)
        call_messages = [*prompt, new_message]
        used = build_memory_trace(chat, long_term, profile)
        request_tokens = self._counter.count_messages([new_message])
        sent_history_tokens = self._counter.count_messages(call_messages) - request_tokens
        if sent_history_tokens + request_tokens > self._config.context_limit_tokens:
            raise ContextLimitExceeded(
                sent_history_tokens + request_tokens,
                self._config.context_limit_tokens,
            )

        started_at = perf_counter()
        response = await self._gateway.complete(call_messages)
        answer = response.text.strip()
        updated_chat = await self._repository.append_exchange(
            chat_id, message, answer, response.usage, used=used
        )

        candidate_tokens = 0
        if command_text is None and self._candidates_enabled:
            extraction = await self._gateway.complete(
                build_candidate_messages(message, answer, long_term, CANDIDATE_LIMIT)
            )
            candidate_tokens = extraction.usage.total_tokens
            candidates = parse_candidates(extraction.text, CANDIDATE_LIMIT)
            if candidates:
                await self._repository.add_candidates(candidates, chat_id)

        system_message = ChatMessage(role="system", content=SYSTEM_PROMPT)
        dialog = build_dialog_usage(
            [system_message, *updated_chat.messages], self._counter, self._config
        )
        long_term_block = build_long_term_block(long_term)
        working_block = build_working_block(updated_chat.working_memory)
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
                memory=MemoryInfo(
                    long_term_count=long_term.total_count(),
                    long_term_tokens=(
                        self._counter.count_messages([long_term_block])
                        if long_term_block
                        else 0
                    ),
                    working_tokens=(
                        self._counter.count_messages([working_block])
                        if working_block
                        else 0
                    ),
                    history_tokens=self._counter.count_messages(updated_chat.messages),
                    candidate_tokens=candidate_tokens + command_tokens,
                    profile_tokens=(
                        self._counter.count_messages([build_profile_block(profile)])
                        if build_profile_block(profile)
                        else 0
                    ),
                ),
            ),
            used=used,
        )