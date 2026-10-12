import json

import pytest

from app.domain.models import RateLimited
from app.presentation.errors import error_response
from app.presentation.schemas import ChatRequest


def test_chat_request_defaults():
    req = ChatRequest(messages=[{"role": "user", "content": "hi"}])
    assert req.stream is False
    assert req.model == ""


def test_chat_request_rejects_unknown_role():
    with pytest.raises(Exception):
        ChatRequest(messages=[{"role": "tool", "content": "hi"}])


def test_error_response_shape_and_retry_after():
    response = error_response(RateLimited("slow down", retry_after=7))
    assert response.status_code == 429
    assert response.headers["retry-after"] == "7"
    payload = json.loads(response.body)
    assert payload["error"]["code"] == "rate_limit_exceeded"
    assert payload["error"]["type"] == "rate_limit_error"
