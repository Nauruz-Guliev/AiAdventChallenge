import httpx
import pytest
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    RateLimitError,
)

from app.domain.models import (
    AuthenticationGatewayError,
    ChatMessage,
    ContextLimitExceeded,
    GatewayTimeoutError,
    LLMGatewayError,
    RateLimitGatewayError,
    TokenUsage,
)
from app.infrastructure.deepseek_gateway import DeepSeekGateway


class FakeCompletions:
    def __init__(self, completion=None, error=None):
        self.completion = completion
        self.error = error
        self.request = None

    async def create(self, **request):
        self.request = request
        if self.error:
            raise self.error
        return self.completion


class FakeClient:
    def __init__(self, completion=None, error=None):
        self.chat = type("Chat", (), {
            "completions": FakeCompletions(completion=completion, error=error),
        })()


def completion(text="adapter answer", model="deepseek-chat", usage="default"):
    usage_object = (
        type("Usage", (), {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        })()
        if usage == "default"
        else usage
    )
    return type("Completion", (), {
        "model": model,
        "usage": usage_object,
        "choices": [type("Choice", (), {
            "message": type("Message", (), {"content": text})(),
        })()],
    })()


@pytest.mark.asyncio
async def test_gateway_sends_openai_compatible_request():
    client = FakeClient(completion())
    gateway = DeepSeekGateway(
        api_key="test",
        base_url="https://example.test/v1",
        model="deepseek-chat",
        client=client,
    )

    response = await gateway.complete([
        ChatMessage(role="user", content="hello"),
    ])

    assert response.text == "adapter answer"
    assert response.model == "deepseek-chat"
    assert response.usage.total_tokens == 15
    assert client.chat.completions.request["model"] == "deepseek-chat"
    assert client.chat.completions.request["messages"] == [
        {"role": "user", "content": "hello"},
    ]


def error_response(status):
    request = httpx.Request("POST", "https://example.test/v1/chat/completions")
    return httpx.Response(status, request=request)


@pytest.mark.asyncio
async def test_gateway_maps_authentication_error():
    error = AuthenticationError("bad key", response=error_response(401), body=None)

    with pytest.raises(AuthenticationGatewayError):
        await DeepSeekGateway(client=FakeClient(error=error)).complete([])


@pytest.mark.asyncio
async def test_gateway_maps_rate_limit_error():
    error = RateLimitError("busy", response=error_response(429), body=None)

    with pytest.raises(RateLimitGatewayError):
        await DeepSeekGateway(client=FakeClient(error=error)).complete([])


@pytest.mark.asyncio
async def test_gateway_maps_timeout_and_connection_errors():
    request = httpx.Request("POST", "https://example.test/v1/chat/completions")

    with pytest.raises(GatewayTimeoutError):
        await DeepSeekGateway(client=FakeClient(error=APITimeoutError(request=request))).complete([])

    with pytest.raises(LLMGatewayError):
        await DeepSeekGateway(client=FakeClient(error=APIConnectionError(request=request))).complete([])


def test_gateway_default_client_is_generous_with_time_and_retries():
    gateway = DeepSeekGateway(api_key="test-key")

    assert gateway._client.max_retries == 2
    assert gateway._client.timeout.read == 180.0
    assert gateway._client.timeout.connect == 15.0
    assert gateway._client.timeout.write == 60.0


@pytest.mark.asyncio
async def test_gateway_rejects_response_without_usage():
    gateway = DeepSeekGateway(client=FakeClient(completion(usage=None)))

    with pytest.raises(LLMGatewayError):
        await gateway.complete([ChatMessage(role="user", content="hello")])


@pytest.mark.asyncio
async def test_gateway_maps_context_length_error():
    error = BadRequestError(
        "context_length_exceeded: maximum context length exceeded",
        response=error_response(400),
        body={"error": {"code": "context_length_exceeded"}},
    )

    with pytest.raises(ContextLimitExceeded):
        await DeepSeekGateway(client=FakeClient(error=error)).complete([])


@pytest.mark.asyncio
async def test_gateway_maps_other_bad_requests_to_gateway_error():
    error = BadRequestError(
        "invalid_request_error: unknown field",
        response=error_response(400),
        body={"error": {"code": "invalid_request_error"}},
    )

    with pytest.raises(LLMGatewayError):
        await DeepSeekGateway(client=FakeClient(error=error)).complete([])
