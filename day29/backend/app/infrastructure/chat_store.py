from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from app.domain.models import ChatState


class JsonChatStore:
    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, chat_id: int) -> Path:
        return self._root / f"{chat_id}.json"

    def load(self, chat_id: int) -> ChatState | None:
        p = self._path(chat_id)
        if not p.exists():
            return None
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        try:
            return ChatState.from_dict(data)
        except (KeyError, ValueError):
            return None

    def save(self, state: ChatState) -> None:
        state.updated_at = datetime.now(timezone.utc).isoformat()
        p = self._path(state.chat_id)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(state.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(tmp, p)

    def delete(self, chat_id: int) -> None:
        p = self._path(chat_id)
        if p.exists():
            p.unlink()

    def list_ids(self) -> list[int]:
        out: list[int] = []
        for p in self._root.glob("*.json"):
            try:
                out.append(int(p.stem))
            except ValueError:
                continue
        return sorted(out)
