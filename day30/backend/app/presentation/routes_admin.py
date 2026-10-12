from __future__ import annotations

import time

from fastapi import APIRouter, Request

from app.presentation.auth import identity_from_request

router = APIRouter()
_START = time.time()


@router.get("/health")
async def health(request: Request) -> dict:
    deps = request.app.state.deps
    up = await deps.service.health()
    return {
        "status": "ok" if up else "degraded",
        "ollama": up,
        "model": deps.settings.default_model,
        "num_ctx": deps.settings.num_ctx,
        "max_tokens_limit": deps.settings.max_tokens_limit,
        "active_requests": deps.guard.active,
        "queued_requests": deps.guard.waiting,
        "uptime_s": round(time.time() - _START, 1),
    }


@router.get("/metrics")
async def metrics(request: Request) -> dict:
    deps = request.app.state.deps
    identity_from_request(request)
    return deps.metrics.snapshot(
        extra={
            "active_requests": deps.guard.active,
            "queued_requests": deps.guard.waiting,
        }
    )
