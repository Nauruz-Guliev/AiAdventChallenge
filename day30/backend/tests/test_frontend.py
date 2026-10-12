from fastapi.testclient import TestClient

from tests.support import make_app, make_settings


def test_index_page_is_served():
    app, _ = make_app(settings=make_settings(frontend_dir="frontend"))
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "Локальный LLM-сервис" in response.text
    assert "app.js" in response.text


def test_static_assets_present():
    app, _ = make_app(settings=make_settings(frontend_dir="frontend"))
    with TestClient(app) as client:
        assert client.get("/app.js").status_code == 200
        assert client.get("/styles.css").status_code == 200
