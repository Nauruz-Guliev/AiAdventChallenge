from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Callable, Optional

_WORD_RE = re.compile(r"\S+")


@dataclass
class Chunk:
    chunk_id: str
    source: str
    title: str
    section: str
    strategy: str
    text: str
    char_offset: int
    token_count: int

    def as_dict(self) -> dict:
        return asdict(self)


def count_tokens(text: str, tokenizer: Optional[Callable[[str], list]] = None) -> int:
    if tokenizer is not None:
        return len(tokenizer(text))
    return len(text.split())


def _word_spans(text: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in _WORD_RE.finditer(text)]


def chunk_fixed(
    text: str,
    chunk_size: int = 512,
    overlap: int = 64,
    source: str = "",
    title: str = "",
    tokenizer=None,
) -> list[Chunk]:
    text = text or ""
    spans = _word_spans(text)
    if not spans:
        return []
    step = max(1, chunk_size - overlap)
    chunks: list[Chunk] = []
    n = len(spans)
    i = 0
    idx = 0
    while i < n:
        j = min(i + chunk_size, n)
        start = spans[i][0]
        end = spans[j - 1][1]
        chunks.append(
            Chunk(
                chunk_id=f"{source}:fixed:{idx}",
                source=source,
                title=title,
                section="fixed",
                strategy="fixed",
                text=text[start:end],
                char_offset=start,
                token_count=j - i,
            )
        )
        idx += 1
        if j == n:
            break
        i += step
    return chunks
