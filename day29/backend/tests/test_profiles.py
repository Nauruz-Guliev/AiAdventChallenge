from app.application.optimization.profiles import (
    PROFILE_ORDER,
    PROFILES,
    QUANTS,
    get_profile,
    get_quant,
    next_profile,
    next_quant,
)


def test_baseline_matches_day28():
    assert PROFILES["baseline"].options == {"num_ctx": 8192}
    assert PROFILES["baseline"].prompt == "baseline"


def test_optimized_uses_tuned_options_and_prompt():
    p = get_profile("optimized")
    assert p.options["temperature"] == 0.2 and p.options["num_predict"] == 512
    assert p.options["num_ctx"] == 4096 and p.prompt == "optimized"


def test_quants_and_cycles():
    assert QUANTS["q8"].model == "gemma4:12b-it-q8_0"
    assert next_profile("baseline") == "params"
    assert next_profile("optimized") == "baseline"
    assert next_quant("q4") == "q8" and next_quant("q8") == "q4"
    assert set(PROFILE_ORDER) == set(PROFILES)
    assert get_quant("q4").model == "gemma4:12b"
