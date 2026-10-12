import pytest

from app.application.chat_service import ChatService
from app.domain.models import ChatMessage, ContextBudgetExceeded, InvalidRequest


class RecordingGateway:
    def __init__(self):
        self.calls = []

    async def chat(self, messages, *, model=None, temperature=None, max_tokens=None, num_ctx=None):
        from app.domain.models import Completion, Usage

        self.calls.append(("chat", model, max_tokens, num_ctx))
        return Completion(text="ok", model=model, usage=Usage.of(1, 1))

    async def stream(self, messages, *, model=None, temperature=None, max_tokens=None, num_ctx=None):
        from app.domain.models import StreamDelta, StreamDone

        self.calls.append(("stream", model, max_tokens, num_ctx))
        yield StreamDelta(text="ok")
        yield StreamDone(model=model, usage=None)

    async def list_models(self):
        return []

    async def health(self):
        return True

    async def loaded_models(self):
        return []


def _service():
    return ChatService(
        RecordingGateway(),
        default_model="gemma4:12b",
        num_ctx=8192,
        max_tokens_default=512,
        max_tokens_limit=2048,
    )


async def test_complete_uses_default_model_and_clamped_tokens():
    service = _service()
    completion = await service.complete([ChatMessage("user", "hi")])
    assert completion.text == "ok"
    assert service._gateway.calls[0] == ("chat", "gemma4:12b", 512, 8192)


async def test_complete_rejects_empty_messages():
    with pytest.raises(InvalidRequest):
        await _service().complete([])


async def test_complete_rejects_bad_role():
    with pytest.raises(InvalidRequest):
        await _service().complete([ChatMessage("tool", "hi")])


async def test_complete_enforces_context_budget():
    with pytest.raises(ContextBudgetExceeded):
        await _service().complete([ChatMessage("user", "a" * 40000)], max_tokens=512)


async def test_stream_validates_eagerly():
    service = _service()
    with pytest.raises(InvalidRequest):
        service.stream([])
