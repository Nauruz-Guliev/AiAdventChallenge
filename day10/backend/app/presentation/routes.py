from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response

from app.application.agent import SYSTEM_PROMPT, Agent
from app.application.compare import ContextComparator
from app.application.ports.chat_repository import ChatRepository
from app.application.ports.token_counter import TokenCounter
from app.application.usage import build_dialog_usage
from app.domain.models import (
    BranchNotFound,
    Chat,
    ChatMessage,
    ChatNotFound,
    ChatSummary,
    LastBranchError,
    UsageConfig,
    UsageReport,
)
from app.presentation.dependencies import (
    get_agent,
    get_repository,
    get_settings,
    get_token_counter,
    get_usage_config,
)
from app.presentation.schemas import (
    ActiveBranchRequest,
    CompareModeResponse,
    BranchCreateRequest,
    BranchResponse,
    ChatDetailResponse,
    ContextResponse,
    FactsUpdateRequest,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatResponse,
    ChatSummaryResponse,
    DialogUsageResponse,
    StageResponse,
    TokenUsageResponse,
    UsageResponse,
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
    dialog = build_dialog_usage(
        [ChatMessage(role="system", content=SYSTEM_PROMPT), *chat.messages],
        counter,
        config,
    )
    return ChatDetailResponse(
        **_summary_response(chat).model_dump(),
        messages=_message_responses(chat.messages),
        branches=[
            BranchResponse(
                id=branch.id,
                name=branch.name,
                fork_at=branch.fork_at,
                facts=dict(branch.facts),
                messages=_message_responses(branch.messages),
            )
            for branch in chat.branches
        ],
        active_branch_id=chat.active_branch_id,
        mode=chat.mode,
        dialog_usage=DialogUsageResponse(**vars(dialog)),
    )


def _message_responses(messages):
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


@router.post("/api/chats/{chat_id}/branches", response_model=ChatDetailResponse)
async def create_branch(
    chat_id: str,
    request: BranchCreateRequest,
    repository: Annotated[ChatRepository, Depends(get_repository)],
) -> ChatDetailResponse:
    try:
        chat = await repository.fork_branch(
            chat_id, request.after_message_index, request.name
        )
    except IndexError as error:
        raise HTTPException(status_code=400, detail="Message index is out of range") from error
    except ChatNotFound as error:
        raise HTTPException(status_code=404, detail="Chat not found") from error
    return await get_chat(chat_id, repository, get_token_counter(), get_usage_config())


@router.patch("/api/chats/{chat_id}/active-branch", response_model=ChatDetailResponse)
async def activate_branch(
    chat_id: str,
    request: ActiveBranchRequest,
    repository: Annotated[ChatRepository, Depends(get_repository)],
) -> ChatDetailResponse:
    try:
        await repository.set_active_branch(chat_id, request.branch_id)
    except (BranchNotFound, ChatNotFound) as error:
        raise HTTPException(status_code=404, detail="Branch not found") from error
    return await get_chat(chat_id, repository, get_token_counter(), get_usage_config())


@router.delete("/api/chats/{chat_id}/branches/{branch_id}", response_model=ChatDetailResponse)
async def remove_branch(
    chat_id: str,
    branch_id: str,
    repository: Annotated[ChatRepository, Depends(get_repository)],
) -> ChatDetailResponse:
    try:
        await repository.delete_branch(chat_id, branch_id)
    except LastBranchError as error:
        raise HTTPException(status_code=409, detail="Cannot delete the last branch") from error
    except (BranchNotFound, ChatNotFound) as error:
        raise HTTPException(status_code=404, detail="Branch not found") from error
    return await get_chat(chat_id, repository, get_token_counter(), get_usage_config())


@router.patch("/api/chats/{chat_id}/facts", response_model=ChatDetailResponse)
async def update_facts(
    chat_id: str,
    request: FactsUpdateRequest,
    repository: Annotated[ChatRepository, Depends(get_repository)],
) -> ChatDetailResponse:
    settings = get_settings()
    capped = dict(list(request.facts.items())[: settings.facts_max_items])
    try:
        await repository.save_facts(chat_id, None, capped)
    except ChatNotFound as error:
        raise HTTPException(status_code=404, detail="Chat not found") from error
    return await get_chat(chat_id, repository, get_token_counter(), get_usage_config())


@router.delete("/api/chats/{chat_id}", status_code=204)
async def delete_chat(
    chat_id: str,
    repository: Annotated[ChatRepository, Depends(get_repository)],
) -> Response:
    await repository.delete_chat(chat_id)
    return Response(status_code=204)


@router.post("/api/chats/{chat_id}/messages", response_model=ChatResponse)
async def send_message(
    chat_id: str,
    request: ChatMessageRequest,
    agent: Annotated[Agent, Depends(get_agent)],
) -> ChatResponse:
    result = await agent.run(chat_id, request.message, mode=request.mode)
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


def _summary_response(chat: Chat | ChatSummary) -> ChatSummaryResponse:
    return ChatSummaryResponse(
        id=chat.id,
        title=chat.title,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
    )


def _usage_response(report: UsageReport) -> UsageResponse:
    data = dict(vars(report))
    context = data.pop("context")
    return UsageResponse(
        **data,
        context=ContextResponse(**vars(context)) if context else None,
    )


@router.post("/api/compare", response_model=list[CompareModeResponse])
async def compare_strategies(
    agent: Annotated[Agent, Depends(get_agent)],
    repository: Annotated[ChatRepository, Depends(get_repository)],
) -> list[CompareModeResponse]:
    results = await ContextComparator(agent, repository).run()
    return [CompareModeResponse(**vars(result)) for result in results]
