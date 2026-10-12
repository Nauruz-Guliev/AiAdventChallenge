from app.config import Settings


def test_defaults():
    s = Settings(_env_file=None, telegram_bot_token="42:ABC")
    assert s.ollama_model == "gemma4:12b"
    assert s.top_k_pre == 30
    assert s.top_k_post == 6
    assert s.think_default is False
    assert s.ollama_options() == {"num_ctx": 8192}


def test_overrides():
    s = Settings(_env_file=None, telegram_bot_token="42:ABC", eval_runs=1, index_path="/tmp/i.json")
    assert s.eval_runs == 1
    assert s.index_path == "/tmp/i.json"
