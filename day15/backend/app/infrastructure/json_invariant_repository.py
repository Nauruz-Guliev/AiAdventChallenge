from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from app.domain.invariant import (
    INVARIANT_CATEGORIES,
    Invariant,
    InvariantNotFound,
)
from app.domain.models import ChatPersistenceError
from app.infrastructure.json_store import read_json_object, write_json_object

_SEED = (
    (
        "Бэкенд — Python (FastAPI), фронтенд — React; новые зависимости не добавляем.",
        "stack",
    ),
    (
        "Состояние задачи ведёт детерминированный автомат на бэкенде, "
        "LLM поставляет только контент.",
        "architecture",
    ),
    (
        "Все запросы к LLM идут через единый шлюз DeepSeekGateway с таймаутами.",
        "decision",
    ),
    (
        "Данные пользователя хранятся только локально в JSON-файлах и наружу "
        "не передаются.",
        "business",
    ),
)


class JsonInvariantRepository:
    def __init__(self, path: Path):
        self._path = path
        self._lock = asyncio.Lock()

    async def list(self) -> list[Invariant]:
        async with self._lock:
            return self._read()

    async def add(self, text: str, category: str) -> Invariant:
        async with self._lock:
            cleaned = text.strip()
            if not cleaned:
                raise ValueError("Invariant text cannot be blank")
            if category not in INVARIANT_CATEGORIES:
                raise ValueError(f"Unknown invariant category: {category}")
            items = self._read()
            invariant = Invariant(
                id=str(uuid.uuid4()), text=cleaned, category=category
            )
            items.append(invariant)
            self._write(items)
            return invariant

    async def remove(self, invariant_id: str) -> None:
        async with self._lock:
            items = self._read()
            if not any(item.id == invariant_id for item in items):
                raise InvariantNotFound(invariant_id)
            self._write([item for item in items if item.id != invariant_id])

    def _read(self) -> list[Invariant]:
        if not self._path.exists():
            return self._seeded()
        try:
            payload = read_json_object(self._path)
        except ChatPersistenceError:
            return _seed()
        raw = payload.get("invariants")
        if not isinstance(raw, list):
            return self._seeded()
        return [
            item
            for item in (
                _from_dict(entry)
                for entry in raw
                if isinstance(entry, dict)
            )
            if item.text
        ]

    def _seeded(self) -> list[Invariant]:
        items = _seed()
        self._write(items)
        return items

    def _write(self, items: list[Invariant]) -> None:
        write_json_object(
            self._path,
            {"version": 1, "invariants": [_to_dict(item) for item in items]},
        )


def _seed() -> list[Invariant]:
    return [
        Invariant(id=str(uuid.uuid4()), text=text, category=category)
        for text, category in _SEED
    ]


def _to_dict(invariant: Invariant) -> dict:
    return {
        "id": invariant.id,
        "text": invariant.text,
        "category": invariant.category,
    }


def _from_dict(payload: dict) -> Invariant:
    category = str(payload.get("category", "decision"))
    return Invariant(
        id=str(payload.get("id") or uuid.uuid4()),
        text=str(payload.get("text", "")).strip(),
        category=category if category in INVARIANT_CATEGORIES else "decision",
    )
