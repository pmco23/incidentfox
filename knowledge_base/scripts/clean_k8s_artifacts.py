#!/usr/bin/env python3
"""
Clean up local Kubernetes datasource artifacts produced by ingestion runs.

By default this script is DRY-RUN and will only print what it would do.

We intentionally keep:
- datasources/k8s/README.md (tracked)
- datasources/k8s/corpus.jsonl (raw-ish normalized corpus)
- datasources/k8s/raw/** (raw docs mirror)

Everything else under datasources/k8s is considered a build artifact (trees, html, logs, samples)
and can be archived or deleted.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

KEEP_ALWAYS = {
    "README.md",
    "corpus.jsonl",
}


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except Exception:
        return False


def should_keep(p: Path) -> bool:
    if p.name in KEEP_ALWAYS:
        return True
    # Keep the raw mirror directory
    if p.is_dir() and p.name == "raw":
        return True
    if "raw" in p.parts:
        return True
    return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--k8s-dir",
        default=str(Path("datasources") / "k8s"),
        help="Path to datasources/k8s (default: datasources/k8s)",
    )
    ap.add_argument(
        "--mode",
        choices=["archive", "delete"],
        default="archive",
        help="archive: move artifacts to datasources/k8s/_archive; delete: remove them (default: archive)",
    )
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Actually perform actions (default is dry-run).",
    )
    args = ap.parse_args(argv)

    k8s_dir = Path(args.k8s_dir)
    if not k8s_dir.exists():
        raise FileNotFoundError(f"Not found: {k8s_dir}")

    archive_dir = k8s_dir / "_archive"
    if args.mode == "archive" and args.apply:
        archive_dir.mkdir(parents=True, exist_ok=True)

    # Consider only top-level children; treat everything but keep-list as artifact.
    candidates = sorted(k8s_dir.iterdir(), key=lambda p: p.name)
    actions: list[tuple[str, Path, Path | None]] = []
    for p in candidates:
        if p.name == "_archive":
            continue
        if should_keep(p):
            continue
        if args.mode == "archive":
            actions.append(("MOVE", p, archive_dir / p.name))
        else:
            actions.append(("DELETE", p, None))

    if not actions:
        print("[clean_k8s_artifacts] nothing to do.")
        return 0

    for kind, src, dst in actions:
        if kind == "MOVE":
            print(
                f"[dry-run] {kind} {src} -> {dst}"
                if not args.apply
                else f"{kind} {src} -> {dst}"
            )
        else:
            print(f"[dry-run] {kind} {src}" if not args.apply else f"{kind} {src}")

    if not args.apply:
        print("")
        print("[clean_k8s_artifacts] dry-run only. Re-run with --apply to execute.")
        return 0

    # Execute
    for kind, src, dst in actions:
        if not _is_under(src, k8s_dir):
            raise RuntimeError(f"Refusing to touch path outside k8s dir: {src}")
        if kind == "MOVE":
            assert dst is not None
            if dst.exists():
                # If already archived, remove the old and replace.
                if dst.is_dir():
                    shutil.rmtree(dst)
                else:
                    dst.unlink()
            shutil.move(str(src), str(dst))
        else:
            if src.is_dir():
                shutil.rmtree(src)
            else:
                src.unlink()

    print(f"[clean_k8s_artifacts] done. mode={args.mode} apply={args.apply}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
