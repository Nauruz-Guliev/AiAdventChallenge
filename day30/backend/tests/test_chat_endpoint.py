import asyncio

import httpx
from fastapi.testclient import TestClient

from app.application.concurrency import OverloadedGuard
from tests.support import FakeGateway, make_app, make_settings

BODY = {"messages": [{"role": "user", "content": "hi"}]}
KEY = {"X-API-Key": "secret"}


def test_completion_ok():
    app, _ = make_app()
    with TestClient(app) as client:
        response = client.post("/v1/chat/completions", json=BODY, headers=KEY)
    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["message"]["content"] == "привет"
    assert body["usage"]["total_tokens"] == 12


def test_completion_requires_key():
    app, _ = make_app()
    with TestClient(app) as client:
        assert client.post("/v1/chat/completions", json=BODY).status_code == 401


def test_completion_rejects_blank_messages():
    app, _ = make_app()
    with TestClient(app) as client:
        response = client.post("/v1/chat/completions", json={"messages": []}, headers=KEY)
    assert response.status_code == 400


def test_context_budget_returns_400():
    app, _ = make_app(settings=make_settings(num_ctx=512, max_tokens_default=512))
    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "a" * 4000}]},
            headers=KEY,
        )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "context_length_exceeded"


def test_rate_limit_returns_429():
    app, _ = make_app(settings=make_settings(rate_limit_burst=2, rate_limit_per_minute=60))
    with TestClient(app) as client:
        assert client.post("/v1/chat/completions", json=BODY, headers=KEY).status_code == 200
        assert client.post("/v1/chat/completions", json=BODY, headers=KEY).status_code == 200
        response = client.post("/v1/chat/completions", json=BODY, headers=KEY)
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limit_exceeded"


async def test_overload_returns_503():
    release = asyncio.Event()

    class SlowGateway(FakeGateway):
        async def chat(self, messages, *, model=None, temperature=None, max_tokens=None, num_ctx=None):
            await release.wait()
            return await super().chat(
                messages, model=model, max_tokens=max_tokens, num_ctx=num_ctx
            )

    app, _ = make_app(
        gateway=SlowGateway(),
        guard=OverloadedGuard(1, 0),
        settings=make_settings(max_concurrency=1, max_queue=0, rate_limit_burst=10),
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first = asyncio.create_task(client.post("/v1/chat/completions", json=BODY, headers=KEY))
        await asyncio.sleep(0.05)
        second = await client.post("/v1/chat/completions", json=BODY, headers=KEY)
        assert second.status_code == 503
        assert second.json()["error"]["code"] == "server_overloaded"
        release.set()
        assert (await first).status_code == 200


def test_metrics_count_requests():
    app, _ = make_app()
    with TestClient(app) as client:
        client.post("/v1/chat/completions", json=BODY, headers=KEY)
        snapshot = client.get("/metrics", headers=KEY).json()
    assert snapshot["requests_total"] == 1
    assert snapshot["success_total"] == 1
    assert snapshot["samples"] == 1
