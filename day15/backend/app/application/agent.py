from time import perf_counter

from app.application.invariant_guard import (
    Violation,
    build_invariants_block,
    build_refusal,
    check_request,
)
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
from app.application.ports.invariant_repository import InvariantRepository
from app.application.ports.llm_gateway import LLMGateway
from app.application.ports.profile_repository import ProfileRepository
from app.application.ports.task_repository import TaskRepository
from app.application.ports.token_counter import TokenCounter
from app.application.profiles import build_profile_block
from app.application.task_engine import (
    PLAN_FORMAT_HINT,
    build_rejection_notice,
    build_task_block,
    parse_proposal,
    render_plan,
)
from app.application.usage import build_dialog_usage, exchange_cost_usd
from app.domain.invariant import Invariant
from app.domain.models import (
    AgentResult,
    AgentStage,
    CandidateConflict,
    ChatMessage,
    ContextLimitExceeded,
    InvalidUserMessage,
    MemoryInfo,
    TokenUsage,
    UsageConfig,
    UsageReport,
    UserProfile,
)
from app.domain.task_state import (
    Event,
    Stage,
    TaskState,
    TransitionRejection,
    attempt,
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
        task_repository: TaskRepository | None = None,
        invariants: InvariantRepository | None = None,
    ):
        self._gateway = gateway
        self._repository = repository
        self._counter = counter
        self._config = config
        self._model = model
        self._candidates_enabled = candidates_enabled
        self._profiles = profiles
        self._task_repository = task_repository
        self._invariants = invariants

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

        state: TaskState | None = None
        if self._task_repository is not None and command_text is None:
            state = await self._task_repository.get()

        invariants: list[Invariant] = []
        if self._invariants is not None and command_text is None:
            invariants = await self._invariants.list()
            if invariants:
                outcome = await check_request(message, invariants, self._gateway)
                if outcome.violation is not None:
                    return await self._refuse(
                        chat_id,
                        message,
                        outcome.violation,
                        invariants,
                        state,
                        outcome.tokens,
                    )

        if self._task_repository is not None and command_text is None:
            if state is None or state.stage == Stage.DONE:
                state = TaskState.start(message)

        new_message = ChatMessage(role="user", content=message)
        prompt = build_prompt(chat, long_term, SYSTEM_PROMPT, profile=profile)
        if state is not None:
            prompt = [
                *prompt,
                ChatMessage(role="system", content=build_task_block(state)),
            ]
        if invariants:
            prompt = [
                *prompt,
                ChatMessage(
                    role="system", content=build_invariants_block(invariants)
                ),
            ]
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
        if state is not None:
            previous_stage = state.stage
            state, rejection, answer = await self._advance_task(
                state, message, answer
            )
            if rejection is not None:
                answer = (
                    f"{build_rejection_notice(rejection, state)}\n\n{answer}"
                )
            elif (
                previous_stage == Stage.PLANNING
                and state.stage == Stage.APPROVAL
            ):
                answer = render_plan(state.steps)
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
            task=state.to_dict() if state is not None else None,
        )

    async def _refuse(
        self,
        chat_id: str,
        message: str,
        violation: Violation,
        invariants: list[Invariant],
        state: TaskState | None,
        tokens: int,
    ) -> AgentResult:
        matched = next(
            (item for item in invariants if item.id == violation.invariant_id),
            None,
        )
        answer = build_refusal(violation, matched)
        await self._repository.append_exchange(
            chat_id, message, answer, TokenUsage(tokens, 0, tokens)
        )
        return AgentResult(
            answer=answer,
            model="guard",
            duration_ms=0,
            stages=[AgentStage(name="Инварианты", status="completed")],
            usage=UsageReport(
                request_tokens=0,
                history_tokens=0,
                response_tokens=0,
                prompt_tokens_api=tokens,
                completion_tokens_api=0,
                total_tokens_api=tokens,
                dialog_total_tokens=0,
                dialog_cost_usd=0.0,
                context_limit=self._config.context_limit_tokens,
                context_remaining=self._config.context_limit_tokens,
                warning=False,
            ),
            violation={
                "invariant_id": violation.invariant_id,
                "reason": violation.reason,
                "invariant": (
                    {
                        "id": matched.id,
                        "text": matched.text,
                        "category": matched.category,
                        "category_label": matched.category_label,
                    }
                    if matched is not None
                    else None
                ),
            },
            task=state.to_dict() if state is not None else None,
        )

    async def _advance_task(
        self, state: TaskState, message: str, answer: str
    ) -> tuple[TaskState, TransitionRejection | None, str]:
        if state.stage == Stage.APPROVAL:
            return state, None, answer
        expected = {
            Stage.PLANNING: Event.PROPOSE_PLAN,
            Stage.EXECUTION: Event.COMPLETE_STEP,
            Stage.VALIDATION: Event.COMPLETE_VALIDATION,
        }[state.stage]
        proposal = parse_proposal(answer, expected)
        if state.stage == Stage.PLANNING:
            steps = proposal.steps
            if steps is None and proposal.event != Event.PROPOSE_PLAN.value:
                new_state, rejection = attempt(state, proposal.event)
                await self._task_repository.save(new_state)
                return new_state, rejection, proposal.text or answer
            if not steps:
                retry = await self._gateway.complete(
                    [
                        ChatMessage(
                            role="system", content=build_task_block(state)
                        ),
                        ChatMessage(role="user", content=message),
                        ChatMessage(role="assistant", content=answer),
                        ChatMessage(role="user", content=PLAN_FORMAT_HINT),
                    ]
                )
                steps = parse_proposal(retry.text, expected).steps
            if not steps:
                await self._task_repository.save(state)
                return state, None, answer
            new_state, rejection = attempt(
                state, Event.PROPOSE_PLAN, steps=steps
            )
        else:
            new_state, rejection = attempt(state, proposal.event)
        if rejection is not None:
            await self._task_repository.save(new_state)
            return new_state, rejection, proposal.text or answer
        await self._task_repository.save(new_state)
        return new_state, None, proposal.text or answer