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


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def _split_sections(markdown: str, title: str, source: str) -> list[tuple[str, str, int]]:
    lines = markdown.splitlines()
    stack: list[tuple[int, str]] = []
    sections: list[tuple[str, str, int]] = []
    buf: list[str] = []
    buf_start = 0
    pos = 0

    def current_path() -> str:
        joined = " > ".join(h for _, h in stack)
        return joined or (title or source or "root")

    def flush() -> None:
        nonlocal buf
        text = "\n".join(buf).strip()
        if text:
            sections.append((current_path(), text, buf_start))
        buf = []

    for line in lines:
        m = _HEADING_RE.match(line)
        if m:
            flush()
            level = len(m.group(1))
            heading = m.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, heading))
            buf_start = pos
            buf = [line]
        else:
            if not buf:
                buf_start = pos
            buf.append(line)
        pos += len(line) + 1
    flush()
    return sections


def chunk_structure(
    markdown: str,
    source: str = "",
    title: str = "",
    min_tokens: int = 128,
    tokenizer=None,
) -> list[Chunk]:
    markdown = markdown or ""
    sections = _split_sections(markdown, title, source)
    merged: list[tuple[str, str, int]] = []
    cur_path = None
    cur_parts: list[str] = []
    cur_off = 0
    for path, text, off in sections:
        if cur_path is None:
            cur_path, cur_off = path, off
        cur_parts.append(text)
        if count_tokens("\n\n".join(cur_parts), tokenizer) >= min_tokens:
            merged.append((cur_path, "\n\n".join(cur_parts), cur_off))
            cur_path, cur_parts, cur_off = None, [], 0
    if cur_parts:
        merged.append((cur_path, "\n\n".join(cur_parts), cur_off))

    chunks: list[Chunk] = []
    for idx, (path, text, off) in enumerate(merged):
        chunks.append(
            Chunk(
                chunk_id=f"{source}:struct:{idx}",
                source=source,
                title=title,
                section=path,
                strategy="structure",
                text=text,
                char_offset=off,
                token_count=count_tokens(text, tokenizer),
            )
        )
    return chunks
