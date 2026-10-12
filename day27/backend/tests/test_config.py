from app.config import Settings


def test_settings_defaults(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "42:ABC")
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    s = Settings(_env_file=None)
    assert s.telegram_bot_token == "42:ABC"
    assert s.ollama_base_url == "http://localhost:11434"
    assert s.ollama_model == "gemma4:12b"
    assert s.history_max_messages == 20
    assert s.request_timeout == 300


def test_settings_ollama_options(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "42:ABC")
    monkeypatch.setenv("OLLAMA_NUM_CTX", "4096")
    s = Settings(_env_file=None)
    assert s.ollama_options() == {"num_ctx": 4096}
