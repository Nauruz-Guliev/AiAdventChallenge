import httpx
import pytest

from app.domain.models import ChatMessage, Role
from app.infrastructure.ollama_client import OllamaClient
from app.ports.llm import StreamDelta

EVAL_NS = 1_000_000_000


@pytest.mark.asyncio
async def test_complete_uses_model_override_and_load_duration():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        seen.update(json.loads(request.content))
        return httpx.Response(200, json={
            "message": {"content": "hi"}, "model": "gemma4:12b-it-q8_0",
            "eval_count": 10, "eval_duration": EVAL_NS, "prompt_eval_count": 3,
            "load_duration": EVAL_NS // 2,
        })

    client = OllamaClient("http://x", "gemma4:12b")
    await client._client.aclose()
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    out = await client.complete(
        [ChatMessage(Role.USER, "q")], model="gemma4:12b-it-q8_0", options={"temperature": 0.2}
    )
    assert seen["model"] == "gemma4:12b-it-q8_0"
    assert seen["options"]["temperature"] == 0.2
    assert out.stats.load_duration_ns == EVAL_NS // 2
    await client.aclose()


@pytest.mark.asyncio
async def test_tags_and_ps():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "gemma4:12b", "size": 8_000_000_000}]})
        return httpx.Response(200, json={"models": [{"name": "gemma4:12b", "size_vram": 5_000_000_000}]})

    client = OllamaClient("http://x", "gemma4:12b")
    await client._client.aclose()
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    assert (await client.tags())[0]["name"] == "gemma4:12b"
    assert (await client.ps())[0]["size_vram"] == 5_000_000_000
    await client.aclose()


@pytest.mark.asyncio
async def test_stream_yields_deltas():
    ndjson = (
        '{"message":{"content":"a"},"done":false}\n'
        '{"message":{"content":"b"},"done":false}\n'
        '{"message":{"content":""},"done":true,"eval_count":2,"eval_duration":%d}\n' % EVAL_NS
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=ndjson.encode())

    client = OllamaClient("http://x", "gemma4:12b")
    await client._client.aclose()
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    kinds = []
    async for ev in client.stream_chat([ChatMessage(Role.USER, "hi")]):
        kinds.append(type(ev).__name__)
        if isinstance(ev, StreamDelta):
            assert ev.kind == "content"
    assert kinds == ["StreamDelta", "StreamDelta", "StreamDone"]
    await client.aclose()
