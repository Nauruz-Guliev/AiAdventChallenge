from app.domain.models import (
    DEFAULT_ACTIVE_PRESET_KEY,
    PROFILE_PRESETS,
    ProfileStore,
    UserProfile,
)


def profile(**overrides):
    data = {
        "id": "p1",
        "title": "Рабочий",
        "tone": "formal",
        "length": "short",
        "structure": "bullets",
        "constraints": ["без эмодзи"],
    }
    data.update(overrides)
    return UserProfile(**data)


def test_profile_with_defaults_is_empty():
    default = UserProfile(id="p1", title="Деловой")
    assert default.is_empty


def test_profile_with_any_preference_is_not_empty():
    assert not profile().is_empty


def test_store_finds_active_profile():
    store = ProfileStore(active_id="p2", profiles=[profile(id="p1"), profile(id="p2")])
    assert store.active().id == "p2"
    assert store.find("nope") is None


def test_presets_include_neutral_business_concise_mentor():
    keys = [preset.key for preset in PROFILE_PRESETS]
    assert keys == ["neutral", "business", "concise", "mentor"]
    assert DEFAULT_ACTIVE_PRESET_KEY == "business"
