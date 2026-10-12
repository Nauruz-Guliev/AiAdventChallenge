from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from app.domain.models import ServiceError


def error_response(error: ServiceError) -> JSONResponse:
    headers: dict[str, str] = {}
    retry_after = getattr(error, "retry_after", None)
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    return JSONResponse(
        status_code=error.status,
        content={
            "error": {
                "message": error.message,
                "type": error.type,
                "code": error.code,
            }
        },
        headers=headers,
    )


async def service_error_handler(request: Request, error: ServiceError) -> JSONResponse:
    return error_response(error)
