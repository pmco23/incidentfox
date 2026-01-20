#!/usr/bin/env python3
"""
Smoke test: run a small OpenAI ingest on a subset of Kubernetes docs, then export HTML.

This is meant to validate the pipeline quickly before running the full rebuild for hours.
"""

from __future__ import annotations

import os
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    os.chdir(repo_root)

    out_tree = Path("datasources/k8s/raptor_tree_smoke_openai.pkl")
    out_html = Path("datasources/k8s/tree_smoke_openai.html")

    cmd_ingest = (
        "PYTHONPATH=. python3 scripts/ingest_k8s.py "
        "--mode openai --progress --smoke "
        "--auto-depth --target-top-nodes 50 "
        "--tb-max-tokens 800 --tb-num-layers 4 --tb-summarization-length 250 "
        "--cluster-max-clusters 8 --cluster-threshold 0.1 --reduction-dimension 6 --cluster-max-length-tokens 8000 "
        "--openai-embed-model text-embedding-3-large "
        "--openai-summarize-model gpt-5.2 "
        "--openai-qa-model gpt-5.2 "
        f"--out-tree {out_tree} "
    )

    cmd_html = (
        "PYTHONPATH=. python3 scripts/visualize_tree_html.py "
        f"--tree {out_tree} --out {out_html}"
    )

    print("[smoke] running ingest...")
    rc = os.system(cmd_ingest)
    if rc != 0:
        print(f"[smoke] ingest failed rc={rc}")
        return 2

    print("[smoke] exporting html...")
    rc = os.system(cmd_html)
    if rc != 0:
        print(f"[smoke] html export failed rc={rc}")
        return 3

    print(f"[smoke] OK tree={out_tree}")
    print(f"[smoke] OK html={out_html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
