#!/usr/bin/env python3
"""
Incrementally update an existing RAPTOR tree pickle with new text.

Example:
  PYTHONPATH=. python3 scripts/incremental_update_tree.py \
    --tree datasources/k8s/raptor_tree.pkl \
    --text-file datasources/k8s/raw/concepts/architecture/_index.md \
    --out-tree datasources/k8s/raptor_tree_updated.pkl \
    --progress
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Optional

from raptor import RetrievalAugmentation, RetrievalAugmentationConfig


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", required=True, help="Path to existing RAPTOR tree pickle")
    ap.add_argument(
        "--text-file", required=True, help="Path to text/markdown file to add"
    )
    ap.add_argument(
        "--out-tree", required=True, help="Where to write updated RAPTOR tree pickle"
    )
    ap.add_argument(
        "--progress", action="store_true", help="Enable extra progress logging"
    )
    ap.add_argument("--similarity-threshold", type=float, default=0.25)
    ap.add_argument("--max-children-for-summary", type=int, default=50)
    ap.add_argument("--max-summary-context-tokens", type=int, default=12000)
    ap.add_argument("--target-top-nodes", type=int, default=75)
    ap.add_argument("--max-layers", type=int, default=5)
    ap.add_argument(
        "--no-rebuild-upper",
        action="store_true",
        help="Disable rebuilding upper layers from layer 1 after applying incremental changes.",
    )
    args = ap.parse_args(argv)

    if args.progress:
        os.environ["RAPTOR_PROGRESS"] = "1"

    text = Path(args.text_file).read_text(encoding="utf-8", errors="replace")

    # Load tree. Config defaults are fine as long as your embeddings/summarizer are compatible.
    ra = RetrievalAugmentation(config=RetrievalAugmentationConfig(), tree=args.tree)
    ra.add_to_existing(
        text,
        similarity_threshold=args.similarity_threshold,
        max_children_for_summary=args.max_children_for_summary,
        max_summary_context_tokens=args.max_summary_context_tokens,
        auto_rebuild_upper_layers=(not args.no_rebuild_upper),
        target_top_nodes=args.target_top_nodes,
        max_layers=args.max_layers,
    )

    out = Path(args.out_tree)
    out.parent.mkdir(parents=True, exist_ok=True)
    ra.save(str(out))
    print(f"[incremental_update_tree] wrote: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
