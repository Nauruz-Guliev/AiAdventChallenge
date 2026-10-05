from __future__ import annotations

import argparse

from embeddings import get_embedder
from index import Hit, IndexStore


def answer(index_path, embedder, query: str, top_k: int = 5) -> list[Hit]:
    store = IndexStore.load(index_path)
    return store.search_text(query, embedder, top_k=top_k)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Semantic search over a local index.")
    parser.add_argument("query")
    parser.add_argument("--index", default="index/structure.json")
    parser.add_argument("--embedder", choices=["fake", "sentence"], default="sentence")
    parser.add_argument("--model", default=None)
    parser.add_argument("--top", type=int, default=5)
    args = parser.parse_args(argv)

    embedder = get_embedder(args.embedder, model=args.model)
    hits = answer(args.index, embedder, args.query, top_k=args.top)
    for i, h in enumerate(hits, 1):
        print(f"{i}. [{h.score:.4f}] {h.source} :: {h.section}")
        print(f"   {h.text[:160].replace(chr(10), ' ')}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
