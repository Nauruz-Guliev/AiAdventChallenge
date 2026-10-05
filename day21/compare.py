from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import pstdev

from index import Hit, IndexStore

DEFAULT_QUERIES = [
    {"query": "how do expect and actual declarations work", "expect": "expect-actual"},
    {"query": "add a library dependency to a multiplatform project", "expect": "add-dependencies"},
    {"query": "sharing code across android ios desktop", "expect": "overview"},
    {"query": "source set hierarchy and intermediate source sets", "expect": "hierarchy"},
    {"query": "ktor http client in multiplatform", "expect": "ktor"},
]


def strategy_stats(store: IndexStore) -> dict:
    sizes = [int(c["token_count"]) for c in store.chunks]
    if not sizes:
        return {
            "num_chunks": 0,
            "total_tokens": 0,
            "avg_tokens": 0.0,
            "min_tokens": 0,
            "max_tokens": 0,
            "std_tokens": 0.0,
        }
    return {
        "num_chunks": len(sizes),
        "total_tokens": sum(sizes),
        "avg_tokens": round(sum(sizes) / len(sizes), 2),
        "min_tokens": min(sizes),
        "max_tokens": max(sizes),
        "std_tokens": round(pstdev(sizes), 2),
    }


def _matches(hit: Hit, expect: str) -> bool:
    haystack = f"{hit.source} {hit.title} {hit.section}".lower()
    return expect.lower() in haystack


def evaluate(store: IndexStore, embedder, queries: list[dict], top_k: int = 3) -> dict:
    details = []
    hits = 0
    for q in queries:
        found = store.search_text(q["query"], embedder, top_k=top_k)
        ok = any(_matches(h, q["expect"]) for h in found)
        hits += int(ok)
        details.append(
            {
                "query": q["query"],
                "expect": q["expect"],
                "hit": ok,
                "top": [
                    {"chunk_id": h.chunk_id, "source": h.source, "section": h.section, "score": round(h.score, 4)}
                    for h in found
                ],
            }
        )
    total = len(queries)
    return {
        "hits": hits,
        "total": total,
        "hit_rate": round(hits / total, 3) if total else 0.0,
        "top_k": top_k,
        "details": details,
    }


def compare_indices(index_dir, embedder, queries=None, top_k: int = 3, report_dir=None) -> dict:
    index_dir = Path(index_dir)
    queries = queries if queries is not None else DEFAULT_QUERIES
    report_dir = Path(report_dir) if report_dir else index_dir
    report: dict = {}
    for strategy in ("fixed", "structure"):
        path = index_dir / f"{strategy}.json"
        if not path.exists():
            continue
        store = IndexStore.load(path)
        report[strategy] = {**strategy_stats(store), **evaluate(store, embedder, queries, top_k=top_k)}

    lines = ["# Сравнение стратегий chunking", ""]
    lines.append("| Метрика | fixed | structure |")
    lines.append("|---|---|---|")
    rows = ["num_chunks", "total_tokens", "avg_tokens", "min_tokens", "max_tokens", "std_tokens", "hit_rate"]
    for row in rows:
        fixed = report.get("fixed", {}).get(row, "—")
        struct = report.get("structure", {}).get(row, "—")
        lines.append(f"| {row} | {fixed} | {struct} |")
    lines.append("")
    for strategy, data in report.items():
        lines.append(f"## {strategy} — детали запросов")
        for d in data.get("details", []):
            mark = "✅" if d["hit"] else "❌"
            lines.append(f"- {mark} `{d['query']}` (ожидали `{d['expect']}`)")
        lines.append("")

    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "comparison.md").write_text("\n".join(lines), encoding="utf-8")
    (report_dir / "comparison.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def main(argv=None) -> int:
    import embeddings as emb

    parser = argparse.ArgumentParser(description="Compare chunking strategies.")
    parser.add_argument("--index", default="index")
    parser.add_argument("--embedder", choices=["fake", "sentence"], default="fake")
    parser.add_argument("--model", default=None)
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args(argv)
    embedder = emb.get_embedder(args.embedder, model=args.model)
    report = compare_indices(args.index, embedder, top_k=args.top_k)
    print(json.dumps(report, ensure_ascii=False, indent=2)[:2000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
