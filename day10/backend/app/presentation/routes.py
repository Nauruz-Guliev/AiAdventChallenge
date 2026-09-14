from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.application.agent import SYSTEM_PROMPT, Agent
from app.application.ports.chat_repository import ChatRepository
from app.application.ports.token_counter import TokenCounter
from app.application.usage import build_dialog_usage
from app.domain.models import Chat, ChatMessage, ChatSummary, UsageConfig, UsageReport
from app.presentation.dependencies import (
    get_agent,
    get_repository,
    get_token_counter,
    get_usage_config,
)
from app.presentation.schemas import (
    ChatDetailResponse,
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
        messages=[
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
            for message in chat.messages
        ],
        dialog_usage=DialogUsageResponse(**vars(dialog)),
    )


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


def _summary_response(chat: Chat | ChatSummary) -> ChatSummaryResponse:
    return ChatSummaryResponse(
        id=chat.id,
        title=chat.title,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
    )


def _usage_response(report: UsageReport) -> UsageResponse:
    return UsageResponse(**vars(report))
