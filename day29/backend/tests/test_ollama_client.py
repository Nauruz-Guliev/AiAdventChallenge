import httpx
import pytest

from app.domain.models import ChatMessage, Role
from app.infrastructure.ollama_client import OllamaClient
from app.ports.llm import StreamDelta

EVAL_NS = 1_000_000_000


@pytest.mark.asyncio
async def test_complete_parses_content_and_stats():
    def handler(request: httpx.Request) -> httpx.Response:
        assert b'"think"' in request.content
        return httpx.Response(200, json={
            "message": {"content": "hello"},
            "model": "gemma4:12b", "eval_count": 10, "eval_duration": EVAL_NS,
            "prompt_eval_count": 3, "total_duration": 2 * EVAL_NS,
        })

    client = OllamaClient("http://x", "gemma4:12b")
    await client._client.aclose()
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    out = await client.complete([ChatMessage(Role.USER, "hi")])
    assert out.text == "hello"
    assert out.stats.completion_tokens == 10
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
