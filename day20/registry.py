from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DAY_DIR = Path(__file__).resolve().parent
ROOT = DAY_DIR.parent


@dataclass(frozen=True)
class ServerSpec:
    name: str
    script: Path


SERVERS: dict[str, ServerSpec] = {
    "weather": ServerSpec("weather", ROOT / "day17" / "server.py"),
    "compose": ServerSpec("compose", ROOT / "day19" / "server.py"),
    "scheduler": ServerSpec("scheduler", ROOT / "day18" / "server.py"),
    "notes": ServerSpec("notes", DAY_DIR / "notes_server.py"),
}
