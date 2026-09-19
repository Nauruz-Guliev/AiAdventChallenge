from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.application.agent import SYSTEM_PROMPT, Agent
from app.application.ports.chat_repository import ChatRepository
from app.application.ports.token_counter import TokenCounter
from app.application.usage import build_dialog_usage
from app.domain.models import (
    LONG_TERM_CATEGORIES,
    CandidateConflict,
    CandidateNotFound,
    Chat,
    ChatMessage,
    ChatNotFound,
    ChatSummary,
    LongTermEntry,
    LongTermEntryNotFound,
    LongTermMemory,
    UsageConfig,
    UsageReport,
    WorkingMemory,
)
from app.presentation.dependencies import (
    get_agent,
    get_repository,
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
    LongTermEntryResponse,
    LongTermRequest,
    LongTermResponse,
    MemoryInfoResponse,
    StageResponse,
    TokenUsageResponse,
    UsageResponse,
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


@router.post("/api/chats/{chat_id}/messages", response_model=ChatResponse)
async def send_message(
    chat_id: str,
    request: ChatMessageRequest,
    agent: Annotated[Agent, Depends(get_agent)],
) -> ChatResponse:
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