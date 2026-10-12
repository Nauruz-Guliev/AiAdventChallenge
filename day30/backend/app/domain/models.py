from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    @classmethod
    def of(cls, prompt: int, completion: int) -> "Usage":
        return cls(prompt, completion, prompt + completion)


@dataclass(frozen=True)
class Completion:
    text: str
    model: str
    usage: Usage


@dataclass(frozen=True)
class StreamDelta:
    text: str


@dataclass(frozen=True)
class StreamDone:
    model: str
    usage: Usage


@dataclass(frozen=True)
class ModelInfo:
    id: str
    parameter_size: str = ""


class ServiceError(Exception):
    """Ошибка, которую презентация превращает в OpenAI-формат."""

    status = 400
    code = "invalid_request_error"
    type = "invalid_request_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidRequest(ServiceError):
    pass


class ContextBudgetExceeded(ServiceError):
    code = "context_length_exceeded"


class Unauthorized(ServiceError):
    status = 401
    code = "invalid_api_key"
    type = "authentication_error"


class RateLimited(ServiceError):
    status = 429
    code = "rate_limit_exceeded"
    type = "rate_limit_error"

    def __init__(self, message: str, retry_after: int = 1) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class Overloaded(ServiceError):
    status = 503
    code = "server_overloaded"
    type = "server_error"

    def __init__(self, message: str, retry_after: int = 1) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class UpstreamUnavailable(ServiceError):
    status = 502
    code = "upstream_unavailable"
    type = "server_error"
