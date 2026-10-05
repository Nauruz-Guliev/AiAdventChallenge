from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

from chunking import chunk_fixed, chunk_structure
from embeddings import Embedder, get_embedder
from index import IndexStore

_HEADING_RE = re.compile(r"^#\s+(.*)$", re.MULTILINE)


@dataclass
class Document:
    source: str
    title: str
    text: str


def load_corpus(corpus_dir) -> list[Document]:
    root = Path(corpus_dir)
    docs: list[Document] = []
    for path in sorted(root.rglob("*.md")):
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue
        m = _HEADING_RE.search(text)
        title = m.group(1).strip() if m else path.stem
        source = path.relative_to(root).as_posix()
        docs.append(Document(source=source, title=title, text=text))
    return docs


def build_index(
    corpus_dir,
    strategy: str,
    embedder: Embedder,
    out_dir,
    tokenizer=None,
    chunk_size: int = 512,
    overlap: int = 64,
    min_tokens: int = 128,
    model_name: str = "unknown",
) -> tuple[IndexStore, Path]:
    if strategy not in ("fixed", "structure"):
        raise ValueError(f"unknown strategy: {strategy!r}")
    docs = load_corpus(corpus_dir)
    chunks = []
    for d in docs:
        if strategy == "fixed":
            chunks.extend(
                chunk_fixed(
                    d.text,
                    chunk_size=chunk_size,
                    overlap=overlap,
                    source=d.source,
                    title=d.title,
                    tokenizer=tokenizer,
                )
            )
        else:
            chunks.extend(
                chunk_structure(
                    d.text,
                    source=d.source,
                    title=d.title,
                    min_tokens=min_tokens,
                    tokenizer=tokenizer,
                )
            )
    store = IndexStore.build(chunks, embedder, model_name=model_name)
    store.meta["strategy"] = strategy
    path = Path(out_dir) / f"{strategy}.json"
    store.save(path)
    return store, path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build a local KMP document index.")
    parser.add_argument("--corpus", default="corpus")
    parser.add_argument("--out", default="index")
    parser.add_argument("--strategy", choices=["fixed", "structure", "both"], default="both")
    parser.add_argument("--embedder", choices=["fake", "sentence"], default="fake")
    parser.add_argument("--model", default=None)
    parser.add_argument("--chunk-size", type=int, default=512)
    parser.add_argument("--overlap", type=int, default=64)
    parser.add_argument("--min-tokens", type=int, default=128)
    args = parser.parse_args(argv)

    embedder = get_embedder(args.embedder, model=args.model)
    if args.embedder == "fake":
        print("ВНИМАНИЕ: используется FakeEmbedder — векторы не семантические.")
    tokenizer = getattr(embedder, "tokenize", None)
    model_name = getattr(embedder, "model_name", args.embedder)

    strategies = ["fixed", "structure"] if args.strategy == "both" else [args.strategy]
    for strategy in strategies:
        store, path = build_index(
            args.corpus,
            strategy,
            embedder,
            args.out,
            tokenizer=tokenizer,
            chunk_size=args.chunk_size,
            overlap=args.overlap,
            min_tokens=args.min_tokens,
            model_name=model_name,
        )
        total_tokens = sum(c["token_count"] for c in store.chunks)
        print(
            f"[{strategy}] chunks={store.meta['num_chunks']} "
            f"tokens={total_tokens} -> {path}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
