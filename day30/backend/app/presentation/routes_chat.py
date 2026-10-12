from __future__ import annotations

import json
import time
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.domain.models import (
    ChatMessage,
    Overloaded,
    RateLimited,
    ServiceError,
    StreamDelta,
    StreamDone,
)
from app.presentation.auth import identity_from_request
from app.presentation.schemas import (
    ChatChunk,
    ChatRequest,
    ChatResponse,
    Choice,
    ChoiceDelta,
    Delta,
    MessageOut,
    ModelCard,
    ModelList,
    UsageOut,
)

router = APIRouter()


def _enforce_rate_limit(request: Request, identity: str) -> None:
    deps = request.app.state.deps
    allowed, retry = deps.limiter.check(identity, time.monotonic())
    if not allowed:
        deps.metrics.inc("rate_limited_total")
        raise RateLimited("Слишком много запросов, сбавь темп", retry_after=retry)


def _messages(body: ChatRequest) -> list[ChatMessage]:
    return [ChatMessage(role=m.role, content=m.content) for m in body.messages]


@router.get("/v1/models")
async def list_models(request: Request) -> ModelList:
    deps = request.app.state.deps
    identity_from_request(request)
    models = await deps.service.list_models()
    return ModelList(data=[ModelCard(id=model.id) for model in models])


# --- chat completions ---


async def chat_completions(request: Request, body: ChatRequest):
    deps = request.app.state.deps
    identity = identity_from_request(request)
    _enforce_rate_limit(request, identity)
    deps.metrics.inc("requests_total")
    messages = _messages(body)
    if body.stream:
        return await _stream(request, body, messages)
    started = time.perf_counter()
    try:
        async with deps.guard.slot():
            completion = await deps.service.complete(
                messages,
                model=body.model or None,
                temperature=body.temperature,
                max_tokens=body.max_tokens,
            )
    except Overloaded:
        deps.metrics.inc("overloaded_total")
        raise
    finally:
        deps.metrics.observe((time.perf_counter() - started) * 1000)
    deps.metrics.inc("success_total")
    return ChatResponse(
        id="chatcmpl-" + uuid.uuid4().hex[:24],
        created=int(time.time()),
        model=completion.model,
        choices=[Choice(message=MessageOut(content=completion.text))],
        usage=UsageOut(
            prompt_tokens=completion.usage.prompt_tokens,
            completion_tokens=completion.usage.completion_tokens,
            total_tokens=completion.usage.total_tokens,
        ),
    )


router.add_api_route("/v1/chat/completions", chat_completions, methods=["POST"])


EOL = chr(10) + chr(10)


async def _stream(request: Request, body: ChatRequest, messages):
    deps = request.app.state.deps
    stream = deps.service.stream(
        messages,
        model=body.model or None,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
    )
    try:
        await deps.guard.acquire()
    except Overloaded:
        deps.metrics.inc("overloaded_total")
        raise
    return StreamingResponse(
        _sse_events(deps, stream, body.model or deps.settings.default_model),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _sse_events(deps, stream, model_name: str):
    chunk_id = "chatcmpl-" + uuid.uuid4().hex[:24]
    created = int(time.time())
    started = time.perf_counter()
    try:
        head = ChatChunk(
            id=chunk_id,
            created=created,
            model=model_name,
            choices=[ChoiceDelta(delta=Delta(role="assistant"))],
        )
        yield "data: " + head.model_dump_json() + EOL
        async for event in stream:
            if isinstance(event, StreamDelta):
                chunk = ChatChunk(
                    id=chunk_id,
                    created=created,
                    model=model_name,
                    choices=[ChoiceDelta(delta=Delta(content=event.text))],
                )
                yield "data: " + chunk.model_dump_json() + EOL
            elif isinstance(event, StreamDone):
                tail = ChatChunk(
                    id=chunk_id,
                    created=created,
                    model=event.model or model_name,
                    choices=[ChoiceDelta(delta=Delta(), finish_reason="stop")],
                )
                yield "data: " + tail.model_dump_json() + EOL
        deps.metrics.inc("success_total")
        yield "data: [DONE]" + EOL
    except ServiceError as error:
        payload = {"error": {"message": error.message, "type": error.type, "code": error.code}}
        yield "data: " + json.dumps(payload, ensure_ascii=False) + EOL
        yield "data: [DONE]" + EOL
    finally:
        deps.metrics.observe((time.perf_counter() - started) * 1000)
        await deps.guard.release()
