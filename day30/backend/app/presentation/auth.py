from __future__ import annotations

from fastapi import Request

from app.domain.models import Unauthorized


def extract_key(header_api_key: str | None, authorization: str | None) -> str | None:
    if header_api_key:
        return header_api_key.strip()
    if authorization:
        parts = authorization.split(None, 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1].strip()
    return None


def authorize(provided: str | None, keys: set[str], *, require: bool) -> str:
    if not keys:
        if require:
            raise Unauthorized("API-ключ не настроен на сервере")
        return "anonymous"
    if not provided or provided not in keys:
        raise Unauthorized("Неверный или отсутствующий API-ключ")
    return f"key:{provided[:6]}"


def identity_from_request(request: Request) -> str:
    deps = request.app.state.deps
    provided = extract_key(
        request.headers.get("x-api-key"),
        request.headers.get("authorization"),
    )
    return authorize(provided, deps.settings.key_set(), require=deps.settings.require_api_key)
