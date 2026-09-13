from typing import Annotated

from fastapi import APIRouter, Depends

from app.application.agent import Agent
from app.presentation.dependencies import get_agent
from app.presentation.schemas import ChatRequest, ChatResponse, StageResponse


router = APIRouter()


@router.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    agent: Annotated[Agent, Depends(get_agent)],
) -> ChatResponse:
    result = await agent.run(request.message)
    return ChatResponse(
        answer=result.answer,
        model=result.model,
        duration_ms=result.duration_ms,
        stages=[
            StageResponse(name=stage.name, status=stage.status)
            for stage in result.stages
        ],
    )
