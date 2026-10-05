from __future__ import annotations

import json
import uuid
from pathlib import Path

from app.domain.models import Message, Session, SessionNotFound, TaskMemory


class SessionStore:
    def __init__(self, directory: str | Path):
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str) -> Path:
        return self._dir / f"{session_id}.json"

    def create(self, goal: str) -> Session:
        session = Session(id=uuid.uuid4().hex, memory=TaskMemory(goal=(goal or "").strip()))
        self.save(session)
        return session

    def get(self, session_id: str) -> Session:
        path = self._path(session_id)
        if not path.exists():
            raise SessionNotFound(f"Сессия не найдена: {session_id}")
        return Session.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def save(self, session: Session) -> None:
        self._path(session.id).write_text(
            json.dumps(session.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def append_message(self, session: Session, message: Message) -> None:
        session.messages.append(message)
        self.save(session)

    def list(self) -> list[dict]:
        result = []
        for path in sorted(self._dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            result.append({
                "id": data["id"],
                "created_at": data.get("created_at", ""),
                "goal": (data.get("memory", {}).get("goal") or ""),
                "n_messages": len(data.get("messages", [])),
            })
        return result
