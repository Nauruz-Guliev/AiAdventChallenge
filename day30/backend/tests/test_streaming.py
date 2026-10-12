import json

from fastapi.testclient import TestClient

from tests.support import make_app

BODY = {"messages": [{"role": "user", "content": "hi"}], "stream": True}
KEY = {"X-API-Key": "secret"}


def _data_lines(text: str) -> list[str]:
    return [line[len("data: "):] for line in text.splitlines() if line.startswith("data: ")]


def test_stream_returns_sse_chunks():
    app, _ = make_app()
    with TestClient(app) as client:
        with client.stream("POST", "/v1/chat/completions", json=BODY, headers=KEY) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            payload = "".join(response.iter_text())
    lines = _data_lines(payload)
    assert lines[-1] == "[DONE]"
    chunks = [json.loads(line) for line in lines[:-1]]
    assert chunks[0]["object"] == "chat.completion.chunk"
    assert chunks[0]["choices"][0]["delta"]["role"] == "assistant"
    text = "".join(c["choices"][0]["delta"].get("content") or "" for c in chunks)
    assert text == "привет"
    assert chunks[-1]["choices"][0]["finish_reason"] == "stop"


def test_stream_requires_key():
    app, _ = make_app()
    with TestClient(app) as client:
        assert client.post("/v1/chat/completions", json=BODY).status_code == 401


def test_stream_rejects_empty_messages_eagerly():
    app, _ = make_app()
    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions", json={"messages": [], "stream": True}, headers=KEY
        )
    assert response.status_code == 400
