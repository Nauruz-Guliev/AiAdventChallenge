import json

import httpx
import pytest

from app.domain.models import ChatMessage, StreamDelta, StreamDone, UpstreamUnavailable
from app.infrastructure.ollama_client import OllamaGateway


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_chat_maps_response_and_usage():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        body = json.loads(request.content)
        assert body["stream"] is False
        assert body["options"]["num_predict"] == 100
        assert body["options"]["num_ctx"] == 4096
        return httpx.Response(
            200,
            json={
                "model": "gemma4:12b",
                "message": {"content": "  привет  "},
                "prompt_eval_count": 7,
                "eval_count": 3,
            },
        )

    gateway = OllamaGateway("http://test", client=_client(handler))
    result = await gateway.chat(
        [ChatMessage("user", "hi")], model="gemma4:12b", max_tokens=100, num_ctx=4096
    )
    assert result.text == "привет"
    assert result.model == "gemma4:12b"
    assert result.usage.total_tokens == 10


async def test_stream_yields_deltas_then_done():
    def handler(request: httpx.Request) -> httpx.Response:
        lines = [
            json.dumps({"message": {"content": "Hel"}, "done": False}),
            json.dumps({"message": {"content": "lo"}, "done": False}),
            json.dumps(
                {
                    "model": "gemma4:12b",
                    "message": {"content": ""},
                    "done": True,
                    "prompt_eval_count": 2,
                    "eval_count": 2,
                }
            ),
        ]
        body = "\n".join(lines) + "\n"
        return httpx.Response(200, content=body.encode())

    gateway = OllamaGateway("http://test", client=_client(handler))
    events = [e async for e in gateway.stream([ChatMessage("user", "hi")], model="gemma4:12b")]
    assert [e.text for e in events if isinstance(e, StreamDelta)] == ["Hel", "lo"]
    done = [e for e in events if isinstance(e, StreamDone)][0]
    assert done.usage.total_tokens == 4


async def test_list_models_and_health():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.40.3"})
        return httpx.Response(
            200,
            json={"models": [{"name": "gemma4:12b", "details": {"parameter_size": "11.9B"}}]},
        )

    gateway = OllamaGateway("http://test", client=_client(handler))
    assert await gateway.health() is True
    models = await gateway.list_models()
    assert models[0].id == "gemma4:12b"
    assert models[0].parameter_size == "11.9B"


async def test_chat_error_becomes_upstream_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    gateway = OllamaGateway("http://test", client=_client(handler))
    with pytest.raises(UpstreamUnavailable):
        await gateway.chat([ChatMessage("user", "hi")], model="gemma4:12b")
