from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.application.chat_service import ChatService
from app.application.concurrency import OverloadedGuard
from app.application.rate_limit import RateLimiter
from app.domain.models import ServiceError
from app.infrastructure.metrics import Metrics
from app.presentation.errors import service_error_handler
from app.presentation.routes_admin import router as admin_router
from app.presentation.routes_chat import router as chat_router


@dataclass
class AppDeps:
    settings: object
    service: ChatService
    metrics: Metrics
    limiter: RateLimiter
    guard: OverloadedGuard


def create_app(settings, service, metrics, limiter, guard, gateway=None) -> FastAPI:
    app = FastAPI(title="День 30 — Приватный LLM-сервис", version="1.0.0")
    app.state.deps = AppDeps(settings, service, metrics, limiter, guard)
    app.state.gateway = gateway

    app.add_exception_handler(ServiceError, service_error_handler)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, error: RequestValidationError):
        message = "; ".join(str(e.get("msg", "")) for e in error.errors())
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "message": f"Некорректный запрос: {message}",
                    "type": "invalid_request_error",
                    "code": "invalid_request_error",
                }
            },
        )

    @app.middleware("http")
    async def add_headers(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = f"{(time.perf_counter() - started) * 1000:.1f}"
        return response

    app.include_router(admin_router)
    app.include_router(chat_router)

    frontend = Path(settings.frontend_dir)
    if frontend.is_dir():
        app.mount("/", StaticFiles(directory=str(frontend), html=True), name="frontend")

    return app
