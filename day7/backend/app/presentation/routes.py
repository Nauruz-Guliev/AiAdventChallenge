from typing import Annotated

from fastapi import APIRouter, Depends

from app.application.ports.chat_repository import ChatRepository
from app.application.agent import Agent
from app.domain.models import Chat, ChatSummary
from app.presentation.dependencies import get_agent, get_repository
from app.presentation.schemas import (
    ChatDetailResponse,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatResponse,
    ChatSummaryResponse,
    StageResponse,
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
) -> ChatDetailResponse:
    chat = await repository.get_chat(chat_id)
    return ChatDetailResponse(
        **_summary_response(chat).model_dump(),
        messages=[
            ChatMessageResponse(role=message.role, content=message.content)
            for message in chat.messages
        ],
    )


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
    )


def _summary_response(chat: Chat | ChatSummary) -> ChatSummaryResponse:
    return ChatSummaryResponse(
        id=chat.id,
        title=chat.title,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
    )
