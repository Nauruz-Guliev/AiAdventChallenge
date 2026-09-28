from __future__ import annotations

import time

import search_api
import storage
import summarizer


def _slugify(text: str) -> str:
    slug = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in text.lower())
    slug = slug.strip("-")
    return slug[:60] or "result"


def _build_search_text(results: list[dict]) -> str:
    return " ".join(f"{r['title']}. {r['snippet']}" for r in results)


def _build_markdown(query: str, results: list[dict], summary: str) -> str:
    lines = [f"# {query}", "", f"Источников: {len(results)}", ""]
    for r in results:
        lines.append(f"- [{r['title']}]({r['url']})")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(summary)
    lines.append("")
    return "\n".join(lines)


def run(query: str, path: str | None = None, sentences: int = 3) -> dict:
    results = search_api.search(query)["results"]
    text = _build_search_text(results)
    sum_result = summarizer.summarize(text, sentences)
    final_md = _build_markdown(query, results, sum_result["summary"])
    if path:
        target = path
    else:
        target = str(storage.DEFAULT_OUT_DIR / f"{int(time.time())}-{_slugify(query)}.md")
    saved = storage.save_to_file(final_md, target)
    return {
        "query": query,
        "stages": {
            "search": {
                "result_count": len(results),
                "top_titles": [r["title"] for r in results[:3]],
            },
            "summarize": {
                "sentence_count": sum_result["sentence_count"],
                "summary_chars": sum_result["summary_chars"],
            },
            "save": {
                "path": saved["path"],
                "bytes_written": saved["bytes_written"],
            },
        },
        "output_path": saved["path"],
        "summary": sum_result["summary"],
    }
