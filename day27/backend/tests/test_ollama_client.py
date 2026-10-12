import json

import httpx
import pytest

from app.domain.models import ChatMessage, Role
from app.infrastructure.ollama_client import OllamaClient
from app.ports.llm import OllamaUnavailable, StreamDelta, StreamDone

NDJSON = "\n".join([
    json.dumps({"message": {"content": "", "thinking": "think1"}, "done": False}),
    json.dumps({"message": {"content": "Hel", "thinking": ""}, "done": False}),
    json.dumps({"message": {"content": "lo"}, "done": False}),
    json.dumps({
        "model": "gemma4:12b", "done": True,
        "prompt_eval_count": 10, "eval_count": 100, "eval_duration": 2_000_000_000,
        "total_duration": 3_000_000_000,
    }),
])


def make_client(handler) -> OllamaClient:
    client = OllamaClient("http://test", timeout=5)
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return client


async def test_stream_chat_events():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        return httpx.Response(200, text=NDJSON)

    c = make_client(handler)
    events = [e async for e in c.stream_chat([ChatMessage(Role.USER, "hi")], "gemma4:12b")]
    kinds = [type(e).__name__ for e in events]
    assert kinds[0] == "StreamDelta" and events[0].kind == "thinking"
    content = "".join(e.text for e in events if isinstance(e, StreamDelta) and e.kind == "content")
    assert content == "Hello"
    done = [e for e in events if isinstance(e, StreamDone)][0]
    assert done.stats.completion_tokens == 100
    assert abs(done.stats.tokens_per_second - 50.0) < 1e-9
    await c.aclose()


async def anext_many(agen):
    async for _ in agen:
        pass


async def test_stream_chat_sends_images():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, text=json.dumps({"message": {"content": "ok"}, "done": True}))

    c = make_client(handler)
    await anext_many(c.stream_chat([ChatMessage(Role.USER, "cap", images=["QkJC"])], "m"))
    assert captured["messages"][0]["images"] == ["QkJC"]
    await c.aclose()


async def test_list_models():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [
            {"name": "gemma4:12b", "details": {"parameter_size": "11.9B"}},
        ]})

    c = make_client(handler)
    models = await c.list_models()
    assert models[0].name == "gemma4:12b"
    assert models[0].parameter_size == "11.9B"
    await c.aclose()


async def test_health_true_and_false():
    c = make_client(lambda r: httpx.Response(200, json={"version": "0.40.3"}))
    assert await c.health() is True
    await c.aclose()

    def boom(request):
        raise httpx.ConnectError("x")

    c2 = make_client(boom)
    assert await c2.health() is False
    await c2.aclose()


async def test_stream_error_raises_unavailable():
    c = make_client(lambda r: httpx.Response(500, text="boom"))
    with pytest.raises(OllamaUnavailable):
        async for _ in c.stream_chat([ChatMessage(Role.USER, "x")], "m"):
            pass
    await c.aclose()
