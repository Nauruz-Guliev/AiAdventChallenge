from __future__ import annotations

import re

from app.domain.models import GenerationStats

TELEGRAM_LIMIT = 4096

_ESCAPE = {"&": "&amp;", "<": "&lt;", ">": "&gt;"}
_ESCAPE_RE = re.compile(r"[&<>]")
_TAG_RE = re.compile(r"<(/?)(\w+)[^>]*>")


def _escape(text: str) -> str:
    return _ESCAPE_RE.sub(lambda m: _ESCAPE[m.group(0)], text)


def md_to_telegram_html(text: str) -> str:
    code_blocks: list[str] = []

    def _stash_block(m: re.Match) -> str:
        code = m.group(1).rstrip("\n")
        code_blocks.append(f"<pre><code>{_escape(code)}</code></pre>")
        return f"\x00{len(code_blocks) - 1}\x00"

    text = re.sub(r"```[^\n]*\n([\s\S]*?)```", _stash_block, text)

    inline: list[str] = []

    def _stash_inline(m: re.Match) -> str:
        inline.append(f"<code>{_escape(m.group(1))}</code>")
        return f"\x01{len(inline) - 1}\x01"

    text = re.sub(r"`([^`\n]+)`", _stash_inline, text)
    text = _escape(text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\x00(\d+)\x00", lambda m: code_blocks[int(m.group(1))], text)
    text = re.sub(r"\x01(\d+)\x01", lambda m: inline[int(m.group(1))], text)

    parts = re.split(r"\n{2,}", text.strip())
    return "\n".join(f"<p>{p.replace(chr(10), '<br>')}</p>" for p in parts if p.strip())


def _close_and_carry(piece: str) -> tuple[str, str]:
    """Закрывает открытые теги в чанке и возвращает их для переноса в следующий."""
    stack: list[str] = []
    for m in _TAG_RE.finditer(piece):
        closing, name = m.group(1), m.group(2).lower()
        if closing:
            if stack and stack[-1] == name:
                stack.pop()
        else:
            stack.append(name)
    closing_tags = "".join(f"</{t}>" for t in reversed(stack))
    carry = "".join(f"<{t}>" for t in stack)
    return piece + closing_tags, carry


def split_message(text: str, limit: int = TELEGRAM_LIMIT) -> list[str]:
    if len(text) <= limit:
        return [text]

    def safe_cut(s: str, start: int, hard_end: int) -> int:
        depth = 0
        last_space = -1
        last_flat = start
        for i in range(start, hard_end):
            ch = s[i]
            if ch == "<":
                depth += 1
            elif ch == ">":
                depth = max(0, depth - 1)
            elif depth == 0:
                last_flat = i + 1
                if ch in "\n ":
                    last_space = i
        if last_space > start:
            return last_space
        if last_flat > start:
            return last_flat
        return hard_end

    chunks: list[str] = []
    pos = 0
    n = len(text)
    carry = ""
    while pos < n:
        end = min(pos + limit, n)
        if end < n:
            end = safe_cut(text, pos, end)
            if end <= pos:
                end = min(pos + limit, n)
        piece = (carry + text[pos:end]).strip() if carry else text[pos:end].strip()
        closed, carry = _close_and_carry(piece)
        chunks.append(closed)
        pos = end
    return [c for c in chunks if c]


def footer(stats: GenerationStats | None, model: str) -> str:
    base = f"🤖 {model} · локально"
    if stats and stats.tokens_per_second > 0:
        return f"{base} · ⚡ {stats.tokens_per_second:.0f} tok/s"
    return base
