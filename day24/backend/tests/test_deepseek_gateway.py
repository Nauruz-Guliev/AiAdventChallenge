import pytest

from app.domain.models import LLMGatewayError
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
        self.chat = type("Chat", (), {"completions": FakeCompletions(completion, error)})()


def completion(text="adapter answer"):
    return type("Completion", (), {
        "choices": [type("Choice", (), {"message": type("Message", (), {"content": text})()})()],
    })()


@pytest.mark.asyncio
async def test_gateway_returns_text():
    client = FakeClient(completion())
    gateway = DeepSeekGateway(api_key="t", client=client)
    assert await gateway.complete([{"role": "user", "content": "hi"}]) == "adapter answer"
    assert client.chat.completions.request["model"] == "deepseek-chat"


@pytest.mark.asyncio
async def test_gateway_maps_error():
    gateway = DeepSeekGateway(api_key="t", client=FakeClient(error=RuntimeError("boom")))
    with pytest.raises(LLMGatewayError):
        await gateway.complete([{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_gateway_rejects_empty():
    gateway = DeepSeekGateway(api_key="t", client=FakeClient(completion("   ")))
    with pytest.raises(LLMGatewayError):
        await gateway.complete([{"role": "user", "content": "hi"}])
