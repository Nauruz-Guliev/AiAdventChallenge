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


def count_tokens(text: str, tokenizer=None) -> int:
    """Число токенов.

    ``tokenizer`` может быть:
    * объектом с методом ``tokenize(text) -> list`` (например, ``Embedder``);
    * вызываемым ``tokenizer(text) -> list``;
    * ``None`` — приблизительно по словам.
    """
    if tokenizer is None:
        return len(text.split())
    if hasattr(tokenizer, "tokenize"):
        return len(tokenizer.tokenize(text))
    if callable(tokenizer):
        return len(tokenizer(text))
    return len(text.split())


def _word_spans(text: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in _WORD_RE.finditer(text)]


def _spans(text: str, tokenizer) -> list[tuple[int, int]]:
    """Границы токенов в символах. У настоящего токенизатора — через offset mapping,
    иначе — по словам."""
    if tokenizer is not None and hasattr(tokenizer, "spans"):
        try:
            spans = tokenizer.spans(text)
        except Exception:  # noqa: BLE001
            spans = None
        if spans:
            return spans
    return _word_spans(text)


def _slice_windows(
    text: str, spans: list[tuple[int, int]], max_tokens: int, overlap: int
) -> list[tuple[str, int, int]]:
    """Нарезает текст на окна по ``max_tokens`` токенов со сдвигом ``overlap``.
    Возвращает список ``(текст, char_offset, token_count)``."""
    if not spans:
        return []
    step = max(1, max_tokens - overlap)
    out: list[tuple[str, int, int]] = []
    n = len(spans)
    i = 0
    while i < n:
        j = min(i + max_tokens, n)
        start = spans[i][0]
        end = spans[j - 1][1]
        out.append((text[start:end], start, j - i))
        if j == n:
            break
        i += step
    return out


def chunk_fixed(
    text: str,
    chunk_size: int = 120,
    overlap: int = 20,
    source: str = "",
    title: str = "",
    tokenizer=None,
) -> list[Chunk]:
    text = text or ""
    spans = _spans(text, tokenizer)
    chunks: list[Chunk] = []
    for idx, (sub, start, token_count) in enumerate(
        _slice_windows(text, spans, chunk_size, overlap)
    ):
        chunks.append(
            Chunk(
                chunk_id=f"{source}:fixed:{idx}",
                source=source,
                title=title,
                section="fixed",
                strategy="fixed",
                text=sub,
                char_offset=start,
                token_count=token_count,
            )
        )
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
    max_tokens: int = 120,
    min_tokens: int = 48,
    tokenizer=None,
) -> list[Chunk]:
    """Чанки по структуре заголовков.

    Секции больше ``max_tokens`` дополнительно режутся на окна, мелкие соседние
    склеиваются до ``min_tokens`` (но не превышая ``max_tokens``)."""
    markdown = markdown or ""
    units: list[tuple[str, str, int, int]] = []
    for path, text, off in _split_sections(markdown, title, source):
        tc = count_tokens(text, tokenizer)
        if tc <= max_tokens:
            units.append((path, text, off, tc))
        else:
            spans = _spans(text, tokenizer)
            for sub, s_off, stc in _slice_windows(text, spans, max_tokens, 0):
                units.append((path, sub, off + s_off, stc))

    chunks: list[Chunk] = []
    cur_path = None
    cur_parts: list[str] = []
    cur_off = 0
    cur_tokens = 0

    def flush() -> None:
        nonlocal cur_path, cur_parts, cur_off, cur_tokens
        if cur_parts:
            chunks.append(
                Chunk(
                    chunk_id=f"{source}:struct:{len(chunks)}",
                    source=source,
                    title=title,
                    section=cur_path,
                    strategy="structure",
                    text="\n\n".join(cur_parts),
                    char_offset=cur_off,
                    token_count=cur_tokens,
                )
            )
        cur_path, cur_parts, cur_off, cur_tokens = None, [], 0, 0

    for path, text, off, tc in units:
        if cur_parts and (cur_tokens >= min_tokens or cur_tokens + tc > max_tokens):
            flush()
        if not cur_parts:
            cur_path, cur_off = path, off
        cur_parts.append(text)
        cur_tokens += tc
    flush()
    return chunks
