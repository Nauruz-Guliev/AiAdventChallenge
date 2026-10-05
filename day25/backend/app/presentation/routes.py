from typing import Annotated

from fastapi import APIRouter, Depends

from app.application.chat_service import ChatService
from app.domain.models import Message, Session
from app.infrastructure.session_store import SessionStore
from app.presentation.dependencies import (
    get_chat_service,
    get_store,
    run_scenarios,
)
from app.presentation.schemas import (
    CitationSchema,
    HitSchema,
    MessageRequestSchema,
    MessageSchema,
    ScenarioReportSchema,
    SessionCreateSchema,
    SessionSchema,
    SessionSummarySchema,
    TaskMemorySchema,
    TurnResponseSchema,
)

router = APIRouter()
_post = router.post
_get = router.get


def _memory_schema(memory) -> TaskMemorySchema:
    return TaskMemorySchema(
        goal=memory.goal,
        clarifications=list(memory.clarifications),
        constraints=list(memory.constraints),
        terms=list(memory.terms),
    )


def _hits_schema(hits) -> list[HitSchema]:
    return [
        HitSchema(
            chunk_id=h.chunk_id, source=h.source, title=h.title,
            section=h.section, score=h.score, text=h.text,
        )
        for h in hits
    ]


def _citations_schema(citations) -> list[CitationSchema]:
    return [
        CitationSchema(
            ref=c.ref, chunk_id=c.chunk_id, source=c.source,
            section=c.section, quote=c.quote, grounded=c.grounded,
        )
        for c in citations
    ]


def _message_schema(m: Message) -> MessageSchema:
    return MessageSchema(
        role=m.role, text=m.text, at=m.at,
        sources=_hits_schema(m.sources), citations=_citations_schema(m.citations),
    )


def _session_schema(s: Session) -> SessionSchema:
    return SessionSchema(
        id=s.id, created_at=s.created_at,
        memory=_memory_schema(s.memory),
        messages=[_message_schema(m) for m in s.messages],
    )


@_post("/api/sessions", response_model=SessionSchema)
async def create_session(
    request: SessionCreateSchema,
    store: Annotated[SessionStore, Depends(get_store)],
) -> SessionSchema:
    return _session_schema(store.create(request.goal))


@_post("/api/sessions/{session_id}/messages", response_model=TurnResponseSchema)
async def send_message(
    session_id: str,
    request: MessageRequestSchema,
    service: Annotated[ChatService, Depends(get_chat_service)],
    store: Annotated[SessionStore, Depends(get_store)],
) -> TurnResponseSchema:
    session = store.get(session_id)
    turn = await service.answer(session, request.text)
    session.messages.append(Message(role="user", text=request.text))
    session.messages.append(Message(
        role="assistant", text=turn.reply,
        sources=list(turn.sources), citations=list(turn.citations),
    ))
    session.memory = turn.memory
    store.save(session)
    return TurnResponseSchema(
        reply=turn.reply, sources=_hits_schema(turn.sources),
        citations=_citations_schema(turn.citations),
        memory=_memory_schema(turn.memory),
        answerable=turn.answerable, relevance=turn.relevance,
    )


@_get("/api/sessions/{session_id}", response_model=SessionSchema)
async def get_session(
    session_id: str,
    store: Annotated[SessionStore, Depends(get_store)],
) -> SessionSchema:
    return _session_schema(store.get(session_id))


@_get("/api/sessions", response_model=list[SessionSummarySchema])
async def list_sessions(
    store: Annotated[SessionStore, Depends(get_store)],
) -> list[SessionSummarySchema]:
    return [SessionSummarySchema(**s) for s in store.list()]


@_post("/api/scenarios/run", response_model=list[ScenarioReportSchema])
async def run_scenarios_endpoint() -> list[ScenarioReportSchema]:
    reports = await run_scenarios()
    return [ScenarioReportSchema(**r.to_dict()) for r in reports]
