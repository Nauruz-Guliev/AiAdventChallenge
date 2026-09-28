from __future__ import annotations

import time
from pathlib import Path

DEFAULT_OUT_DIR = Path(__file__).with_name("out")


class StorageError(Exception):
    """Ошибка записи файла."""


def save_to_file(content: str, path: str | None = None) -> dict:
    if path:
        target = Path(path).resolve()
    else:
        target = (DEFAULT_OUT_DIR / f"{int(time.time())}-note.md").resolve()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        data = content.encode("utf-8")
        target.write_bytes(data)
    except OSError as exc:
        raise StorageError(f"Не удалось записать файл: {exc}") from exc
    return {
        "path": str(target),
        "bytes_written": len(data),
        "written_at": int(time.time()),
    }
