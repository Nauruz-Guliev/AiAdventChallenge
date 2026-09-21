import hashlib
import os
import ssl
import tempfile
import urllib.request
from pathlib import Path

import tiktoken

from app.domain.models import ChatMessage

PER_MESSAGE_OVERHEAD_TOKENS = 4

_ENCODING_BLOBS = {
    "cl100k_base": (
        "https://openaipublic.blob.core.windows.net/"
        "encodings/cl100k_base.tiktoken"
    ),
}


def ensure_encoding_cached(encoding_name: str, timeout: int = 60) -> Path:
    """Download the tiktoken BPE file into the tiktoken cache.

    tiktoken downloads the file with ``requests``/``certifi``, which fails
    behind corporate TLS interception. Python's default SSL context trusts
    the system store (and honours ``SSL_CERT_FILE``), so we seed the cache
    ourselves; tiktoken then loads offline.
    """
    blob = _ENCODING_BLOBS[encoding_name]
    cache_dir = Path(
        os.environ.get(
            "TIKTOKEN_CACHE_DIR",
            Path(tempfile.gettempdir()) / "data-gym-cache",
        )
    )
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / hashlib.sha1(blob.encode("utf-8")).hexdigest()
    if cache_path.exists() and cache_path.is_file():
        return cache_path
    with urllib.request.urlopen(
        blob, context=ssl.create_default_context(), timeout=timeout
    ) as response:
        payload = response.read()
    temporary = cache_path.with_suffix(".part")
    temporary.write_bytes(payload)
    temporary.replace(cache_path)
    return cache_path


class TiktokenCounter:
    """Локальная оценка токенов.

    У DeepSeek собственный токенизатор, cl100k_base даёт приближение,
    поэтому все числа из этого класса — оценка, а не биллинг.
    """

    def __init__(self, encoding_name: str = "cl100k_base"):
        ensure_encoding_cached(encoding_name)
        self._encoding = tiktoken.get_encoding(encoding_name)

    def count_text(self, text: str) -> int:
        return len(self._encoding.encode(text))

    def count_messages(self, messages: list[ChatMessage]) -> int:
        return sum(
            self.count_text(message.content) + PER_MESSAGE_OVERHEAD_TOKENS
            for message in messages
        )
