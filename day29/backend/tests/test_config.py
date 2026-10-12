from app.config import Settings


def test_defaults():
    s = Settings(_env_file=None, telegram_bot_token="42:ABC")
    assert s.default_profile == "optimized"
    assert s.default_quant == "q4"
    assert s.ollama_model_q8 == "gemma4:12b-it-q8_0"
    assert s.ab_full_questions == 10 and s.ab_runs == 2
    assert s.ollama_options() == {"num_ctx": 8192}


def test_overrides():
    s = Settings(_env_file=None, telegram_bot_token="42:ABC", default_profile="baseline", ab_runs=1)
    assert s.default_profile == "baseline" and s.ab_runs == 1
