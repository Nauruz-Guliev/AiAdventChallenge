import json
import os
import tempfile
from pathlib import Path

from app.domain.models import ChatPersistenceError


def read_json_object(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ChatPersistenceError(f"Cannot read {path.name}") from error
    if not isinstance(payload, dict):
        raise ChatPersistenceError(f"Invalid format in {path.name}")
    return payload


def write_json_object(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as temporary:
            json.dump(payload, temporary, ensure_ascii=False, indent=2)
            temporary.write("\n")
            temp_path = temporary.name
        os.replace(temp_path, path)
    except OSError as error:
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)
        raise ChatPersistenceError(f"Cannot write {path.name}") from error
