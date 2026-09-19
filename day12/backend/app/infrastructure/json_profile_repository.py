import asyncio
import uuid
from pathlib import Path

from app.domain.models import (
    DEFAULT_ACTIVE_PRESET_KEY,
    PROFILE_PRESETS,
    ProfileConflict,
    ProfileNotFound,
    ProfileStore,
    UserProfile,
)
from app.infrastructure.json_store import read_json_object, write_json_object


class JsonProfileRepository:
    def __init__(self, profiles_path: Path):
        self._profiles_path = profiles_path
        self._lock = asyncio.Lock()

    async def get_store(self) -> ProfileStore:
        async with self._lock:
            return self._read_store()

    async def get_active(self) -> UserProfile | None:
        async with self._lock:
            return self._read_store().active()

    async def create(self, profile: UserProfile) -> UserProfile:
        async with self._lock:
            store = self._read_store()
            store.profiles.append(profile)
            if not store.active_id:
                store.active_id = profile.id
            self._write_store(store)
            return profile

    async def update(self, profile_id: str, fields: dict) -> UserProfile:
        async with self._lock:
            store = self._read_store()
            profile = store.find(profile_id)
            if profile is None:
                raise ProfileNotFound(profile_id)
            for key, value in fields.items():
                setattr(profile, key, value)
            self._write_store(store)
            return profile

    async def delete(self, profile_id: str) -> None:
        async with self._lock:
            store = self._read_store()
            profile = store.find(profile_id)
            if profile is None:
                raise ProfileNotFound(profile_id)
            if len(store.profiles) == 1:
                raise ProfileConflict("cannot delete the last profile")
            store.profiles = [
                item for item in store.profiles if item.id != profile_id
            ]
            if store.active_id == profile_id:
                store.active_id = store.profiles[0].id
            self._write_store(store)

    async def activate(self, profile_id: str) -> UserProfile:
        async with self._lock:
            store = self._read_store()
            profile = store.find(profile_id)
            if profile is None:
                raise ProfileNotFound(profile_id)
            store.active_id = profile_id
            self._write_store(store)
            return profile

    def _read_store(self) -> ProfileStore:
        if not self._profiles_path.exists():
            store = _seed_store()
            self._write_store(store)
            return store
        payload = read_json_object(self._profiles_path)
        profiles = [
            _profile_from_dict(item) for item in payload.get("profiles", [])
        ]
        if not profiles:
            store = _seed_store()
            self._write_store(store)
            return store
        active_id = str(payload.get("active_id", ""))
        if not any(item.id == active_id for item in profiles):
            active_id = profiles[0].id
        return ProfileStore(active_id=active_id, profiles=profiles)

    def _write_store(self, store: ProfileStore) -> None:
        write_json_object(
            self._profiles_path,
            {
                "version": 1,
                "active_id": store.active_id,
                "profiles": [_profile_to_dict(item) for item in store.profiles],
            },
        )


def _seed_store() -> ProfileStore:
    profiles = [
        UserProfile(
            id=str(uuid.uuid4()),
            title=preset.label,
            tone=preset.tone,
            length=preset.length,
            structure=preset.structure,
            constraints=list(preset.constraints),
        )
        for preset in PROFILE_PRESETS
    ]
    active_id = profiles[0].id
    for preset, profile in zip(PROFILE_PRESETS, profiles):
        if preset.key == DEFAULT_ACTIVE_PRESET_KEY:
            active_id = profile.id
    return ProfileStore(active_id=active_id, profiles=profiles)


def _profile_to_dict(profile: UserProfile) -> dict:
    return {
        "id": profile.id,
        "title": profile.title,
        "name": profile.name,
        "role": profile.role,
        "language": profile.language,
        "tone": profile.tone,
        "length": profile.length,
        "structure": profile.structure,
        "constraints": list(profile.constraints),
    }


def _profile_from_dict(payload: dict) -> UserProfile:
    return UserProfile(
        id=str(payload.get("id", "")),
        title=str(payload.get("title", "")),
        name=str(payload.get("name", "")),
        role=str(payload.get("role", "")),
        language=str(payload.get("language", "ru")),
        tone=str(payload.get("tone", "neutral")),
        length=str(payload.get("length", "medium")),
        structure=str(payload.get("structure", "prose")),
        constraints=[str(item) for item in payload.get("constraints", [])],
    )
