from app.config import Settings


def test_defaults():
    s = Settings(_env_file=None)
    assert s.host == "0.0.0.0"
    assert s.port == 8000
    assert s.num_ctx == 8192
    assert s.max_tokens_default == 512
    assert s.max_tokens_limit == 2048
    assert s.max_concurrency == 1
    assert s.key_set() == set()


def test_key_set_parses_and_trims():
    s = Settings(_env_file=None, api_keys=" a, b ,,c ")
    assert s.key_set() == {"a", "b", "c"}
