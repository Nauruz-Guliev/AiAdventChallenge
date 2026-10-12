from fastapi.testclient import TestClient

from tests.support import FakeGateway, make_app


def test_health_ok():
    app, _ = make_app()
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["model"] == "gemma4:12b"
    assert body["num_ctx"] == 8192
    assert body["active_requests"] == 0


def test_health_degraded_when_ollama_down():
    app, _ = make_app(gateway=FakeGateway(fail_health=True))
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "degraded"


def test_models_requires_key():
    app, _ = make_app()
    with TestClient(app) as client:
        response = client.get("/v1/models")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_api_key"


def test_models_returns_list_with_key():
    app, _ = make_app()
    with TestClient(app) as client:
        response = client.get("/v1/models", headers={"X-API-Key": "secret"})
    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "list"
    assert body["data"][0]["id"] == "gemma4:12b"


def test_request_id_header_present():
    app, _ = make_app()
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": "abc123"})
    assert response.headers["x-request-id"] == "abc123"
