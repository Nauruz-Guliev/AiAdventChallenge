from __future__ import annotations

import re

from app.domain.models import Citation, Hit

_MARKER = re.compile(r"\[(\d+)\]")


def parse_markers(text: str) -> list[int]:
    refs: list[int] = []
    seen: set[int] = set()
    for match in _MARKER.finditer(text or ""):
        n = int(match.group(1))
        if n >= 1 and n not in seen:
            seen.add(n)
            refs.append(n)
    return refs


def lcs(a: str, b: str) -> str:
    a, b = a or "", b or ""
    if not a or not b:
        return ""
    la, lb = len(a), len(b)
    prev = [0] * (lb + 1)
    best_len, best_end = 0, 0
    for i in range(1, la + 1):
        cur = [0] * (lb + 1)
        for j in range(1, lb + 1):
            if a[i - 1] == b[j - 1]:
                cur[j] = prev[j - 1] + 1
                if cur[j] > best_len:
                    best_len, best_end = cur[j], i
        prev = cur
    return a[best_end - best_len:best_end]


def extract_citations(text: str, hits: list[Hit], min_quote_len: int = 24) -> list[Citation]:
    refs = parse_markers(text)
    citations: list[Citation] = []
    for n in refs:
        if n > len(hits):
            continue
        h = hits[n - 1]
        quote = lcs(text, h.text).strip()
        citations.append(Citation(
            ref=n, chunk_id=h.chunk_id, source=h.source, section=h.section,
            quote=quote, grounded=len(quote) >= min_quote_len,
        ))
    return citations
