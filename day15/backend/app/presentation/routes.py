import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.application.agent import SYSTEM_PROMPT, Agent
from app.application.ports.chat_repository import ChatRepository
from app.application.ports.invariant_repository import InvariantRepository
from app.application.ports.profile_repository import ProfileRepository
from app.application.ports.task_repository import TaskRepository
from app.application.ports.token_counter import TokenCounter
from app.application.profiles import normalize_profile_fields
from app.application.task_engine import APPROVAL_NOTICE, PAUSE_NOTICE
from app.application.usage import build_dialog_usage
from app.domain.models import (
    LONG_TERM_CATEGORIES,
    PROFILE_PRESETS,
    CandidateConflict,
    CandidateNotFound,
    Chat,
    ChatMessage,
    ChatNotFound,
    ChatSummary,
    LongTermEntry,
    LongTermEntryNotFound,
    LongTermMemory,
    ProfileConflict,
    ProfileNotFound,
    UsageConfig,
    UsageReport,
    UserProfile,
    WorkingMemory,
)
from app.domain.invariant import Invariant, InvariantNotFound
from app.domain.task_state import (
    ALLOWED_TRANSITIONS,
    DONE_ACTION,
    EVENT_LABELS,
    EVENT_STAGE,
    STAGE_LABELS,
    STAGE_ORDER,
    STAGES,
    Event,
    Stage,
    TaskState,
    attempt,
)
from app.presentation.dependencies import (
    get_agent,
    get_invariant_repository,
    get_profile_repository,
    get_repository,
    get_task_repository,
    get_token_counter,
    get_usage_config,
)
from app.presentation.schemas import (
    CandidateApproveRequest,
    CandidateResponse,
    ChatDetailResponse,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatResponse,
    ChatSummaryResponse,
    DialogUsageResponse,
    InvariantCreateRequest,
    InvariantResponse,
    LongTermEntryResponse,
    LongTermRequest,
    LongTermResponse,
    MemoryInfoResponse,
    ProfileCreateRequest,
    ProfileFromPresetRequest,
    ProfilePresetResponse,
    ProfileResponse,
    ProfileStoreResponse,
    ProfileUpdateRequest,
    EventOptionResponse,
    StageOptionResponse,
    StageResponse,
    TaskStateResponse,
    TokenUsageResponse,
    TransitionInfoResponse,
    TransitionRejectionResponse,
    TransitionRequest,
    TransitionsResponse,
    UsageResponse,
    UsedMemoryResponse,
    UsedProfileResponse,
    UsedWorkingMemoryResponse,
    ViolationResponse,
    WorkingMemoryRequest,
    WorkingMemoryResponse,
)


router = APIRouter()


@router.post("/api/chats", response_model=ChatSummaryResponse, status_code=201)
async def create_chat(
    repository: Annotated[ChatRepository, Depends(get_repository)],
) -> ChatSummaryResponse:
    return _summary_response(await repository.create_chat())


@router.get("/api/chats", response_model=list[ChatSummaryResponse])
async def list_chats(
    repository: Annotated[ChatRepository, Depends(get_repository)],
) -> list[ChatSummaryResponse]:
    return [_summary_response(chat) for chat in await repository.list_chats()]


@router.get("/api/chats/{chat_id}", response_model=ChatDetailResponse)
async def get_chat(
    chat_id: str,
    repository: Annotated[ChatRepository, Depends(get_repository)],
    counter: Annotated[TokenCounter, Depends(get_token_counter)],
    config: Annotated[UsageConfig, Depends(get_usage_config)],
) -> ChatDetailResponse:
    chat = await repository.get_chat(chat_id)
    return _detail_response(chat, counter, config)


@router.delete("/api/chats/{chat_id}", status_code=204)
async def delete_chat(
    chat_id: str,
    repository: Annotated[ChatRepository, Depends(get_repository)],
) -> Response:
    await repository.delete_chat(chat_id)
    return Response(status_code=204)


@router.delete("/api/chats/{chat_id}/messages", response_model=ChatDetailResponse)
async def clear_history(
    chat_id: str,
    repository: Annotated[ChatRepository, Depends(get_repository)],
    counter: Annotated[TokenCounter, Depends(get_token_counter)],
    config: Annotated[UsageConfig, Depends(get_usage_config)],
) -> ChatDetailResponse:
    chat = await repository.clear_messages(chat_id)
    return _detail_response(chat, counter, config)


@router.get(
    "/api/chats/{chat_id}/working-memory",
    response_model=WorkingMemoryResponse,
)
async def get_working_memory(
    chat_id: str,
    repository: Annotated[ChatRepository, Depends(get_repository)],
) -> WorkingMemoryResponse:
    working = await repository.get_working_memory(chat_id)
    return WorkingMemoryResponse(**_working_dict(working))


@router.put(
    "/api/chats/{chat_id}/working-memory",
    response_model=ChatDetailResponse,
)
async def save_working_memory(
    chat_id: str,
    request: WorkingMemoryRequest,
    repository: Annotated[ChatRepository, Depends(get_repository)],
    counter: Annotated[TokenCounter, Depends(get_token_counter)],
    config: Annotated[UsageConfig, Depends(get_usage_config)],
) -> ChatDetailResponse:
    working = WorkingMemory(
        goal=request.goal,
        constraints=list(request.constraints),
        decisions=list(request.decisions),
        status=request.status,
    )
    chat = await repository.save_working_memory(chat_id, working)
    return _detail_response(chat, counter, config)


@router.post(
    "/api/chats/{chat_id}/working-memory/complete",
    response_model=ChatDetailResponse,
)
async def complete_working_memory(
    chat_id: str,
    repository: Annotated[ChatRepository, Depends(get_repository)],
    counter: Annotated[TokenCounter, Depends(get_token_counter)],
    config: Annotated[UsageConfig, Depends(get_usage_config)],
) -> ChatDetailResponse:
    chat = await repository.complete_working_memory(chat_id)
    return _detail_response(chat, counter, config)


@router.post(
    "/api/chats/{chat_id}/working-memory/reset",
    response_model=ChatDetailResponse,
)
async def reset_working_memory(
    chat_id: str,
    repository: Annotated[ChatRepository, Depends(get_repository)],
    counter: Annotated[TokenCounter, Depends(get_token_counter)],
    config: Annotated[UsageConfig, Depends(get_usage_config)],
) -> ChatDetailResponse:
    chat = await repository.reset_working_memory(chat_id)
    return _detail_response(chat, counter, config)


@router.get("/api/long-term", response_model=LongTermResponse)
async def get_long_term(
    repository: Annotated[ChatRepository, Depends(get_repository)],
) -> LongTermResponse:
    return _long_term_response(await repository.get_long_term())


@router.put("/api/long-term", response_model=LongTermResponse)
async def replace_long_term(
    request: LongTermRequest,
    repository: Annotated[ChatRepository, Depends(get_repository)],
    config: Annotated[UsageConfig, Depends(get_usage_config)],
) -> LongTermResponse:
    for category in LONG_TERM_CATEGORIES:
        entries = getattr(request, category)
        if len(entries) > config.long_term_max_per_category:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Категория {category} превышает лимит "
                    f"{config.long_term_max_per_category} записей."
                ),
            )
        for entry in entries:
            if len(entry.text) > config.long_term_max_item_chars:
                raise HTTPException(
                    status_code=400,
                    detail="Запись долговременной памяти слишком длинная.",
                )
    long_term = LongTermMemory(
        profile=[LongTermEntry(**entry.model_dump()) for entry in request.profile],
        decisions=[
            LongTermEntry(**entry.model_dump()) for entry in request.decisions
        ],
        knowledge=[
            LongTermEntry(**entry.model_dump()) for entry in request.knowledge
        ],
    )
    return _long_term_response(await repository.replace_long_term(long_term))


@router.delete(
    "/api/long-term/{category}/{entry_id}",
    status_code=204,
)
async def delete_long_term_entry(
    category: str,
    entry_id: str,
    repository: Annotated[ChatRepository, Depends(get_repository)],
) -> Response:
    if category not in LONG_TERM_CATEGORIES:
        raise HTTPException(
            status_code=404, detail="Неизвестная категория памяти"
        )
    try:
        await repository.delete_long_term_entry(category, entry_id)
    except LongTermEntryNotFound as error:
        raise HTTPException(
            status_code=404, detail="Запись памяти не найдена"
        ) from error
    return Response(status_code=204)


@router.get("/api/profiles/presets", response_model=list[ProfilePresetResponse])
async def list_profile_presets() -> list[ProfilePresetResponse]:
    return [
        ProfilePresetResponse(
            key=preset.key,
            label=preset.label,
            tone=preset.tone,
            length=preset.length,
            structure=preset.structure,
            constraints=list(preset.constraints),
        )
        for preset in PROFILE_PRESETS
    ]


@router.get("/api/profiles", response_model=ProfileStoreResponse)
async def get_profiles(
    profiles: Annotated[ProfileRepository, Depends(get_profile_repository)],
) -> ProfileStoreResponse:
    store = await profiles.get_store()
    return ProfileStoreResponse(
        active_id=store.active_id,
        profiles=[_profile_response(item) for item in store.profiles],
    )


@router.get("/api/profile", response_model=ProfileResponse)
async def get_active_profile(
    profiles: Annotated[ProfileRepository, Depends(get_profile_repository)],
) -> ProfileResponse:
    profile = await profiles.get_active()
    if profile is None:
        raise HTTPException(status_code=404, detail="Активный профиль не найден")
    return _profile_response(profile)


@router.post("/api/profiles", response_model=ProfileResponse, status_code=201)
async def create_profile(
    request: ProfileCreateRequest,
    profiles: Annotated[ProfileRepository, Depends(get_profile_repository)],
    config: Annotated[UsageConfig, Depends(get_usage_config)],
) -> ProfileResponse:
    fields = normalize_profile_fields(request.model_dump())
    _validate_profile_fields(fields, config)
    profile = UserProfile(id=str(uuid.uuid4()), **fields)
    return _profile_response(await profiles.create(profile))


@router.post(
    "/api/profiles/from-preset", response_model=ProfileResponse, status_code=201
)
async def create_profile_from_preset(
    request: ProfileFromPresetRequest,
    profiles: Annotated[ProfileRepository, Depends(get_profile_repository)],
) -> ProfileResponse:
    preset = next(
        (item for item in PROFILE_PRESETS if item.key == request.key), None
    )
    if preset is None:
        raise HTTPException(status_code=404, detail="Пресет не найден")
    profile = UserProfile(
        id=str(uuid.uuid4()),
        title=preset.label,
        tone=preset.tone,
        length=preset.length,
        structure=preset.structure,
        constraints=list(preset.constraints),
    )
    return _profile_response(await profiles.create(profile))


@router.put("/api/profiles/{profile_id}", response_model=ProfileResponse)
async def update_profile(
    profile_id: str,
    request: ProfileUpdateRequest,
    profiles: Annotated[ProfileRepository, Depends(get_profile_repository)],
    config: Annotated[UsageConfig, Depends(get_usage_config)],
) -> ProfileResponse:
    fields = normalize_profile_fields(
        {
            key: value
            for key, value in request.model_dump().items()
            if value is not None
        }
    )
    _validate_profile_fields(fields, config)
    try:
        profile = await profiles.update(profile_id, fields)
    except ProfileNotFound as error:
        raise HTTPException(
            status_code=404, detail="Профиль не найден"
        ) from error
    return _profile_response(profile)


@router.delete("/api/profiles/{profile_id}", status_code=204)
async def delete_profile(
    profile_id: str,
    profiles: Annotated[ProfileRepository, Depends(get_profile_repository)],
) -> Response:
    try:
        await profiles.delete(profile_id)
    except ProfileNotFound as error:
        raise HTTPException(
            status_code=404, detail="Профиль не найден"
        ) from error
    except ProfileConflict as error:
        raise HTTPException(
            status_code=400, detail="Нельзя удалить последний профиль"
        ) from error
    return Response(status_code=204)


@router.post(
    "/api/profiles/{profile_id}/activate", response_model=ProfileResponse
)
async def activate_profile(
    profile_id: str,
    profiles: Annotated[ProfileRepository, Depends(get_profile_repository)],
) -> ProfileResponse:
    try:
        profile = await profiles.activate(profile_id)
    except ProfileNotFound as error:
        raise HTTPException(
            status_code=404, detail="Профиль не найден"
        ) from error
    return _profile_response(profile)


@router.get("/api/candidates", response_model=list[CandidateResponse])
async def list_candidates(
    repository: Annotated[ChatRepository, Depends(get_repository)],
    status: str | None = Query(default="pending"),
) -> list[CandidateResponse]:
    return [
        CandidateResponse(**vars(candidate))
        for candidate in await repository.list_candidates(status)
    ]


@router.post(
    "/api/candidates/{candidate_id}/approve",
    response_model=LongTermEntryResponse,
)
async def approve_candidate(
    candidate_id: str,
    repository: Annotated[ChatRepository, Depends(get_repository)],
    request: CandidateApproveRequest | None = None,
) -> LongTermEntryResponse:
    category = request.category if request else None
    text = request.text if request else None
    if category is not None and category not in LONG_TERM_CATEGORIES:
        raise HTTPException(status_code=400, detail="Неизвестная категория памяти")
    if text is not None and not text.strip():
        raise HTTPException(status_code=400, detail="Текст записи не может быть пустым")
    try:
        entry = await repository.approve_candidate(
            candidate_id, category=category, text=text
        )
    except CandidateNotFound as error:
        raise HTTPException(
            status_code=404, detail="Кандидат не найден"
        ) from error
    except CandidateConflict as error:
        raise HTTPException(
            status_code=409, detail="Кандидат уже обработан или дублируется"
        ) from error
    return LongTermEntryResponse(**vars(entry))


@router.post(
    "/api/candidates/{candidate_id}/reject",
    response_model=CandidateResponse,
)
async def reject_candidate(
    candidate_id: str,
    repository: Annotated[ChatRepository, Depends(get_repository)],
) -> CandidateResponse:
    try:
        candidate = await repository.reject_candidate(candidate_id)
    except CandidateNotFound as error:
        raise HTTPException(
            status_code=404, detail="Кандидат не найден"
        ) from error
    except CandidateConflict as error:
        raise HTTPException(
            status_code=409, detail="Кандидат уже обработан"
        ) from error
    return CandidateResponse(**vars(candidate))


@router.delete("/api/candidates", status_code=200)
async def clear_rejected_candidates(
    repository: Annotated[ChatRepository, Depends(get_repository)],
    status: str = Query(default="rejected"),
) -> dict:
    if status != "rejected":
        raise HTTPException(
            status_code=400, detail="Очищать можно только отклонённых кандидатов"
        )
    removed = await repository.clear_rejected_candidates()
    return {"removed": removed}


@router.get("/api/task/state", response_model=TaskStateResponse)
async def get_task_state(
    tasks: Annotated[TaskRepository, Depends(get_task_repository)],
) -> TaskStateResponse:
    return _task_response(await tasks.get())


@router.post("/api/task/pause", response_model=TaskStateResponse)
async def pause_task(
    tasks: Annotated[TaskRepository, Depends(get_task_repository)],
) -> TaskStateResponse:
    state = await tasks.get()
    if state is None:
        return _task_response(None)
    state = state.pause()
    await tasks.save(state)
    return _task_response(state)


@router.post("/api/task/resume", response_model=TaskStateResponse)
async def resume_task(
    tasks: Annotated[TaskRepository, Depends(get_task_repository)],
) -> TaskStateResponse:
    state = await tasks.get()
    if state is None:
        return _task_response(None)
    state = state.resume()
    await tasks.save(state)
    return _task_response(state)


@router.get("/api/task/transitions", response_model=TransitionsResponse)
async def get_transitions() -> TransitionsResponse:
    return TransitionsResponse(
        stages=[
            StageOptionResponse(key=item["key"], label=item["label"])
            for item in STAGES
        ],
        events=[
            EventOptionResponse(
                event=event.value,
                label=EVENT_LABELS[event],
                stage=EVENT_STAGE[event].value,
            )
            for event in Event
        ],
        transitions=[
            TransitionInfoResponse(
                stage=stage.value,
                label=STAGE_LABELS[stage],
                allowed=[target.value for target in targets],
            )
            for stage, targets in ALLOWED_TRANSITIONS.items()
        ],
    )


@router.post("/api/task/transition", response_model=TaskStateResponse)
async def apply_transition(
    request: TransitionRequest,
    tasks: Annotated[TaskRepository, Depends(get_task_repository)],
) -> TaskStateResponse:
    state = await tasks.get()
    if state is None:
        raise HTTPException(status_code=409, detail="Нет активной задачи")
    if state.paused:
        raise HTTPException(status_code=409, detail="Задача на паузе")
    new_state, rejection = attempt(state, request.event)
    if rejection is not None:
        await tasks.save(new_state)
        raise HTTPException(
            status_code=409,
            detail={
                "reason": rejection.reason,
                "from_stage": rejection.from_stage,
                "to_stage": rejection.to_stage,
            },
        )
    await tasks.save(new_state)
    return _task_response(new_state)


@router.post("/api/chats/{chat_id}/messages", response_model=ChatResponse)
async def send_message(
    chat_id: str,
    request: ChatMessageRequest,
    agent: Annotated[Agent, Depends(get_agent)],
    tasks: Annotated[TaskRepository, Depends(get_task_repository)],
) -> ChatResponse:
    state = await tasks.get()
    if state is not None and state.paused:
        return ChatResponse(
            chat_id=chat_id,
            answer=PAUSE_NOTICE,
            model="—",
            duration_ms=0,
            stages=[StageResponse(name="Задача на паузе", status="completed")],
            usage=_zero_usage(),
            task=_task_response(state),
        )
    if state is not None and state.stage == Stage.APPROVAL:
        return ChatResponse(
            chat_id=chat_id,
            answer=APPROVAL_NOTICE,
            model="—",
            duration_ms=0,
            stages=[
                StageResponse(name="План ждёт утверждения", status="completed")
            ],
            usage=_zero_usage(),
            task=_task_response(state),
        )
    result = await agent.run(chat_id, request.message)
    return ChatResponse(
        chat_id=chat_id,
        answer=result.answer,
        model=result.model,
        duration_ms=result.duration_ms,
        stages=[
            StageResponse(name=stage.name, status=stage.status)
            for stage in result.stages
        ],
        usage=_usage_response(result.usage),
        used=_used_response(result.used),
        task=TaskStateResponse(**result.task) if result.task else None,
        violation=(
            ViolationResponse(**result.violation)
            if result.violation
            else None
        ),
    )


@router.get("/api/invariants", response_model=list[InvariantResponse])
async def list_invariants(
    invariants: Annotated[
        InvariantRepository, Depends(get_invariant_repository)
    ],
) -> list[InvariantResponse]:
    return [_invariant_response(item) for item in await invariants.list()]


@router.post(
    "/api/invariants", response_model=InvariantResponse, status_code=201
)
async def create_invariant(
    request: InvariantCreateRequest,
    invariants: Annotated[
        InvariantRepository, Depends(get_invariant_repository)
    ],
) -> InvariantResponse:
    invariant = await invariants.add(request.text, request.category)
    return _invariant_response(invariant)


@router.delete("/api/invariants/{invariant_id}", status_code=204)
async def delete_invariant(
    invariant_id: str,
    invariants: Annotated[
        InvariantRepository, Depends(get_invariant_repository)
    ],
) -> Response:
    try:
        await invariants.remove(invariant_id)
    except InvariantNotFound as error:
        raise HTTPException(
            status_code=404, detail="Инвариант не найден"
        ) from error
    return Response(status_code=204)


def _invariant_response(invariant: Invariant) -> InvariantResponse:
    return InvariantResponse(
        id=invariant.id,
        text=invariant.text,
        category=invariant.category,
        category_label=invariant.category_label,
    )


def _task_response(state: TaskState | None) -> TaskStateResponse:
    if state is None:
        return TaskStateResponse(active=False, expected_action=DONE_ACTION)
    return TaskStateResponse(
        active=True,
        task=state.task,
        stage=state.stage.value,
        stage_index=STAGE_ORDER.index(state.stage),
        step=state.step_number,
        total_steps=state.total_steps,
        step_label=state.step_label,
        expected_action=state.expected_action,
        paused=state.paused,
        steps=list(state.steps),
        allowed_stages=[stage.value for stage in state.allowed_stages],
        rejections=[
            TransitionRejectionResponse(
                event=rejection.event,
                from_stage=rejection.from_stage,
                to_stage=rejection.to_stage,
                reason=rejection.reason,
            )
            for rejection in state.rejections
        ],
    )


def _zero_usage() -> UsageResponse:
    return UsageResponse(
        request_tokens=0,
        history_tokens=0,
        response_tokens=0,
        prompt_tokens_api=0,
        completion_tokens_api=0,
        total_tokens_api=0,
        dialog_total_tokens=0,
        dialog_cost_usd=0.0,
        context_limit=0,
        context_remaining=0,
        warning=False,
        memory=None,
    )


def _used_response(used: dict | None) -> UsedMemoryResponse | None:
    if not used:
        return None
    working = used.get("working")
    profile = used.get("profile")
    return UsedMemoryResponse(
        history_count=used.get("history_count", 0),
        profile=UsedProfileResponse(**profile) if profile else None,
        working=UsedWorkingMemoryResponse(**working) if working else None,
        long_term=used.get("long_term", {}),
    )


def _profile_response(profile: UserProfile) -> ProfileResponse:
    return ProfileResponse(**vars(profile))


def _validate_profile_fields(fields: dict, config: UsageConfig) -> None:
    title = fields.get("title")
    if title is not None and (not title.strip() or len(title) > 60):
        raise HTTPException(
            status_code=400,
            detail="Название профиля должно быть от 1 до 60 символов",
        )
    constraints = fields.get("constraints")
    if constraints is None:
        return
    if len(constraints) > config.profile_max_constraints:
        raise HTTPException(
            status_code=400, detail="Слишком много ограничений профиля"
        )
    if any(len(item) > config.profile_max_item_chars for item in constraints):
        raise HTTPException(
            status_code=400, detail="Ограничение профиля слишком длинное"
        )


def _working_dict(working: WorkingMemory) -> dict:
    return {
        "goal": working.goal,
        "constraints": list(working.constraints),
        "decisions": list(working.decisions),
        "status": working.status,
    }


def _summary_response(chat: Chat | ChatSummary) -> ChatSummaryResponse:
    return ChatSummaryResponse(
        id=chat.id,
        title=chat.title,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
    )


def _message_responses(messages) -> list[ChatMessageResponse]:
    return [
        ChatMessageResponse(
            role=message.role,
            content=message.content,
            usage=(
                TokenUsageResponse(
                    prompt_tokens=message.usage.prompt_tokens,
                    completion_tokens=message.usage.completion_tokens,
                    total_tokens=message.usage.total_tokens,
                )
                if message.usage
                else None
            ),
            used=_used_response(message.used),
        )
        for message in messages
    ]


def _detail_response(
    chat: Chat, counter: TokenCounter, config: UsageConfig
) -> ChatDetailResponse:
    dialog = build_dialog_usage(
        [ChatMessage(role="system", content=SYSTEM_PROMPT), *chat.messages],
        counter,
        config,
    )
    return ChatDetailResponse(
        **_summary_response(chat).model_dump(),
        messages=_message_responses(chat.messages),
        working_memory=WorkingMemoryResponse(**_working_dict(chat.working_memory)),
        dialog_usage=DialogUsageResponse(**vars(dialog)),
    )


def _long_term_response(long_term: LongTermMemory) -> LongTermResponse:
    def entries(items):
        return [LongTermEntryResponse(**vars(item)) for item in items]

    return LongTermResponse(
        profile=entries(long_term.profile),
        decisions=entries(long_term.decisions),
        knowledge=entries(long_term.knowledge),
    )


def _usage_response(report: UsageReport) -> UsageResponse:
    data = dict(vars(report))
    memory = data.pop("memory")
    return UsageResponse(
        **data,
        memory=MemoryInfoResponse(**vars(memory)) if memory else None,
    )