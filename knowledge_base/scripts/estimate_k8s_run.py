#!/usr/bin/env python3
"""
Estimate the scale (tokens/chunks) of ingesting a corpus into RAPTOR.

This does NOT call any external APIs.

Inputs:
- datasources/k8s/corpus.jsonl (produced by scripts/k8s_fetch_docs.py)

Outputs:
- doc count, total characters
- approximate total tokens (cl100k_base via tiktoken)
- estimated chunk count using RAPTOR's split_text() (per-doc) for a chosen tb_max_tokens

Why this helps:
- Embedding work is ~1 call per chunk.
- Tree building will also perform clustering + summarization per layer; the number of summaries is data-dependent,
  but you can treat it as "some thousands" once you see chunk_count at full scale.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, Optional

import tiktoken
from raptor.utils import split_text


def iter_corpus_jsonl(path: Path, max_docs: Optional[int] = None) -> Iterable[dict]:
    n = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            n += 1
            if max_docs is not None and n > max_docs:
                break
            yield json.loads(line)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--corpus",
        default=str(Path("datasources") / "k8s" / "corpus.jsonl"),
        help="Path to corpus.jsonl (default: datasources/k8s/corpus.jsonl)",
    )
    ap.add_argument(
        "--max-docs",
        type=int,
        default=None,
        help="Optional cap on number of docs (useful for sampling)",
    )
    ap.add_argument(
        "--tb-max-tokens",
        type=int,
        default=400,
        help="Chunk size used by RAPTOR split_text (default: 400)",
    )
    args = ap.parse_args(argv)

    corpus_path = Path(args.corpus)
    if not corpus_path.exists():
        raise FileNotFoundError(
            f"Corpus not found: {corpus_path}. Run scripts/k8s_fetch_docs.py first."
        )

    enc = tiktoken.get_encoding("cl100k_base")

    doc_count = 0
    total_chars = 0
    total_tokens = 0
    total_chunks = 0

    for rec in iter_corpus_jsonl(corpus_path, max_docs=args.max_docs):
        doc_count += 1
        text = rec.get("text", "") or ""
        total_chars += len(text)
        total_tokens += len(enc.encode(text))

        # Mirror RAPTOR chunking behavior (per doc) for chunk-count estimation
        chunks = split_text(text, enc, args.tb_max_tokens)
        total_chunks += len(chunks)

    print("[estimate_k8s_run] docs:", doc_count)
    print("[estimate_k8s_run] total_chars:", total_chars)
    print("[estimate_k8s_run] approx_total_tokens(cl100k_base):", total_tokens)
    print("[estimate_k8s_run] tb_max_tokens:", args.tb_max_tokens)
    print("[estimate_k8s_run] estimated_leaf_chunks:", total_chunks)
    print("")
    print("Heuristics:")
    print("- Embedding calls ~= leaf_chunks (if using OpenAI embeddings).")
    print(
        "- Cluster summaries are data-dependent; for large corpora, expect O(thousands) summaries per layer."
    )
    print(
        "- RAPTOR clustering tries to keep each cluster under ~3500 tokens before summarization (see RAPTOR_Clustering)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
