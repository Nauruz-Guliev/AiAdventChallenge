from __future__ import annotations

import json
import os
import time
from pathlib import Path

from mcp.server import MCPServer

mcp = MCPServer("notes")

NOTES_PATH = Path(os.environ.get("NOTES_DB", Path(__file__).with_name("notes.json")))


def _load() -> list[dict]:
    if not NOTES_PATH.exists():
        return []
    try:
        return json.loads(NOTES_PATH.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return []


def _save(notes: list[dict]) -> None:
    try:
        NOTES_PATH.parent.mkdir(parents=True, exist_ok=True)
        NOTES_PATH.write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Не удалось сохранить заметки: {exc}") from exc


@mcp.tool()
def add_note(title: str, body: str) -> dict:
    """Добавить заметку.

    Args:
        title: Заголовок заметки.
        body: Текст заметки.
    """
    notes = _load()
    note = {"id": len(notes) + 1, "title": title, "body": body, "created_at": int(time.time())}
    notes.append(note)
    _save(notes)
    return note


@mcp.tool()
def list_notes() -> dict:
    """Список всех заметок."""
    return {"notes": _load()}


@mcp.tool()
def search_notes(query: str) -> dict:
    """Поиск заметок по подстроке в заголовке или тексте.

    Args:
        query: Строка поиска (регистронезависимо).
    """
    q = query.lower()
    matches = [n for n in _load() if q in n["title"].lower() or q in n["body"].lower()]
    return {"query": query, "matches": matches}


if __name__ == "__main__":
    mcp.run()
