from __future__ import annotations

import base64

DEFAULT_PHOTO_PROMPT = "Опиши изображение"


def encode_photo(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def photo_prompt(caption: str | None) -> str:
    return (caption or "").strip() or DEFAULT_PHOTO_PROMPT
