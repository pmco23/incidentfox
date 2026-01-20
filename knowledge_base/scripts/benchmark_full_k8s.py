#!/usr/bin/env python3
"""
Benchmark a full Kubernetes-docs ingest + QA eval run and write a single report JSON.

What it records:
- Build scale: docs, chars, estimated chunks (offline estimate)
- Build time: wall clock seconds (from ingest log + timer)
- OpenAI usage: tokens & durations (if RAPTOR_USAGE_LOG_PATH enabled)
- QA quality: pass/fail on a curated preset (writes JSON)
- Summarizer red-flags: count of debug events (guard/truncation) if enabled
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


def _run(
    cmd: list[str], *, env: dict | None = None, out_path: Path | None = None
) -> int:
    if out_path is None:
        return subprocess.call(cmd, env=env)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        p = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT, env=env)
        return int(p.wait())


_INGEST_DOCS_RE = re.compile(
    r"\\[ingest_k8s\\]\\s+mode=\\S+\\s+docs=(\\d+)\\s+chars=(\\d+)"
)
_INGEST_SECONDS_RE = re.compile(r"\\[ingest_k8s\\]\\s+build_seconds=(\\d+\\.\\d+)")


def _parse_ingest_log(path: Path) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if not path.exists():
        return out
    text = path.read_text(encoding="utf-8", errors="replace")
    m = _INGEST_DOCS_RE.search(text)
    if m:
        out["docs"] = int(m.group(1))
        out["chars"] = int(m.group(2))
    m2 = _INGEST_SECONDS_RE.search(text)
    if m2:
        out["build_seconds"] = float(m2.group(1))
    return out


def _sum_usage_jsonl(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0}
    by_kind: Dict[str, Dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        kind = str(rec.get("kind", "unknown"))
        pt = int(rec.get("prompt_tokens", 0) or 0)
        ct = int(rec.get("completion_tokens", 0) or 0)
        tt = int(rec.get("total_tokens", 0) or 0)
        total["prompt_tokens"] += pt
        total["completion_tokens"] += ct
        total["total_tokens"] += tt
        total["calls"] += 1
        slot = by_kind.setdefault(
            kind,
            {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0},
        )
        slot["prompt_tokens"] += pt
        slot["completion_tokens"] += ct
        slot["total_tokens"] += tt
        slot["calls"] += 1
    return {"total": total, "by_kind": by_kind}


def _count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    n = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip():
            n += 1
    return n


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--corpus", default=str(Path("datasources") / "k8s" / "corpus.jsonl")
    )
    ap.add_argument(
        "--run-dir",
        default=None,
        help="Output run directory (default: datasources/k8s/runs/full_<ts>/)",
    )
    ap.add_argument("--tb-summary-profile", default="chapter-summary")
    ap.add_argument("--tb-max-tokens", type=int, default=600)
    ap.add_argument("--tb-num-layers", type=int, default=6)
    ap.add_argument("--auto-depth", action="store_true", default=True)
    ap.add_argument("--target-top-nodes", type=int, default=75)
    ap.add_argument("--openai-embed-model", default="text-embedding-3-large")
    ap.add_argument("--openai-summarize-model", default="gpt-5.2")
    ap.add_argument("--openai-qa-model", default="gpt-5.2")
    ap.add_argument("--embed-max-workers", type=int, default=8)
    ap.add_argument("--summary-max-workers", type=int, default=6)
    ap.add_argument("--cache-embeddings", action="store_true", default=True)
    ap.add_argument("--cache-summaries", action="store_true", default=True)
    ap.add_argument("--extract-keywords", action="store_true", default=True)
    ap.add_argument("--keywords-min-layer", type=int, default=2)
    ap.add_argument("--keywords-max", type=int, default=12)
    ap.add_argument(
        "--compress-context", choices=["none", "extractive", "llm"], default="llm"
    )
    ap.add_argument("--top-k", type=int, default=40)
    ap.add_argument("--max-context-tokens", type=int, default=9000)
    ap.add_argument("--qa-max-context-tokens", type=int, default=3500)
    ap.add_argument("--preset", default="k8s_full_curated_v1")
    args = ap.parse_args(argv)

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_dir = (
        Path(args.run_dir)
        if args.run_dir
        else Path("datasources") / "k8s" / "runs" / f"full_{ts}"
    )
    run_dir.mkdir(parents=True, exist_ok=True)

    # Paths
    out_tree = run_dir / "k8s_full.pkl"
    out_html = run_dir / "k8s_full.html"
    ingest_log = run_dir / "build.log"
    estimate_log = run_dir / "estimate.txt"
    summary_debug = run_dir / "summary_debug.jsonl"
    usage_log = run_dir / "usage.jsonl"
    qa_json = run_dir / "qa_results.json"
    report_json = run_dir / "report.json"

    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path.cwd())

    # 1) Offline scale estimate
    _run(
        [
            "python3",
            "scripts/estimate_k8s_run.py",
            "--corpus",
            str(args.corpus),
            "--tb-max-tokens",
            str(args.tb_max_tokens),
        ],
        env=env,
        out_path=estimate_log,
    )

    # 2) Full ingest
    t0 = time.time()
    ingest_cmd = [
        "python3",
        "-u",
        "scripts/ingest_k8s.py",
        "--mode",
        "openai",
        "--progress",
        "--corpus",
        str(args.corpus),
        "--chunk-per-doc",
        "--chunking",
        "markdown",
        "--tb-summary-profile",
        str(args.tb_summary_profile),
        "--auto-depth",
        "--target-top-nodes",
        str(args.target_top_nodes),
        "--tb-max-tokens",
        str(args.tb_max_tokens),
        "--tb-num-layers",
        str(args.tb_num_layers),
        "--openai-embed-model",
        str(args.openai_embed_model),
        "--openai-summarize-model",
        str(args.openai_summarize_model),
        "--openai-qa-model",
        str(args.openai_qa_model),
        "--cache-embeddings",
        "--embedding-cache-path",
        str(
            Path("datasources")
            / "k8s"
            / ".cache"
            / f"embeddings-{args.openai_embed_model.replace('/', '_')}.sqlite"
        ),
        "--embed-max-workers",
        str(args.embed_max_workers),
        "--cache-summaries",
        "--summary-cache-path",
        str(
            Path("datasources")
            / "k8s"
            / ".cache"
            / f"summaries-{args.openai_summarize_model.replace('/', '_')}.sqlite"
        ),
        "--summary-max-workers",
        str(args.summary_max_workers),
        "--summary-debug-log-path",
        str(summary_debug),
        "--summary-debug-events",
        "guard,truncation",
        "--summary-debug-max-chars",
        "0",
        "--usage-log-path",
        str(usage_log),
        "--extract-keywords",
        "--keywords-min-layer",
        str(args.keywords_min_layer),
        "--keywords-max",
        str(args.keywords_max),
        "--out-tree",
        str(out_tree),
        "--export-html",
        "--out-html",
        str(out_html),
        "--html-title",
        f"K8s Full ({args.tb_summary_profile})",
    ]

    ingest_rc = _run(ingest_cmd, env=env, out_path=ingest_log)
    wall_build_s = float(time.time() - t0)

    # 3) QA eval
    qa_cmd = [
        "python3",
        "scripts/ask_tree.py",
        "--tree",
        str(out_tree),
        "--preset",
        str(args.preset),
        "--top-k",
        str(args.top_k),
        "--max-context-tokens",
        str(args.max_context_tokens),
        "--compress-context",
        str(args.compress_context),
        "--qa-max-context-tokens",
        str(args.qa_max_context_tokens),
        "--json-out",
        str(qa_json),
    ]
    qa_log = run_dir / "qa.log"
    qa_rc = _run(qa_cmd, env=env, out_path=qa_log)

    # 4) Build report
    ingest_parsed = _parse_ingest_log(ingest_log)
    usage_summary = _sum_usage_jsonl(usage_log)

    qa_data: Dict[str, Any] = {}
    if qa_json.exists():
        try:
            qa_data = json.loads(qa_json.read_text(encoding="utf-8"))
        except Exception:
            qa_data = {}
    cases = qa_data.get("cases") or []
    pass_n = sum(1 for c in cases if c.get("ok") is True)
    fail_n = sum(1 for c in cases if c.get("ok") is False)

    report: Dict[str, Any] = {
        "run_dir": str(run_dir),
        "timestamp_utc": ts,
        "ingest": {
            "exit_code": int(ingest_rc),
            "wall_seconds": wall_build_s,
            **ingest_parsed,
        },
        "artifacts": {
            "tree_pickle": str(out_tree),
            "tree_pickle_bytes": out_tree.stat().st_size if out_tree.exists() else None,
            "html": str(out_html),
            "html_bytes": out_html.stat().st_size if out_html.exists() else None,
            "build_log": str(ingest_log),
            "estimate_log": str(estimate_log),
        },
        "summarizer_debug": {
            "path": str(summary_debug),
            "events_count": _count_jsonl(summary_debug),
        },
        "usage": {
            "path": str(usage_log),
            **usage_summary,
        },
        "qa": {
            "preset": str(args.preset),
            "exit_code": int(qa_rc),
            "results_json": str(qa_json),
            "pass": int(pass_n),
            "fail": int(fail_n),
        },
    }
    report_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"[benchmark_full_k8s] wrote report: {report_json}")
    return 0 if (ingest_rc == 0 and qa_rc == 0) else 2


if __name__ == "__main__":
    raise SystemExit(main())
