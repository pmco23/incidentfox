#!/usr/bin/env python3
"""
Fetch Kubernetes docs into a local folder under /datasources/k8s.

Default source: kubernetes/website GitHub repo zip (main branch).

Outputs:
- datasources/k8s/raw/...            (copied markdown/mdx files)
- datasources/k8s/corpus.jsonl       (one JSON per file: id, rel_path, source_url, text)

This script requires network access when you run it locally.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional, Tuple

K8S_WEBSITE_REPO = "kubernetes/website"
DEFAULT_REF = "main"


@dataclass(frozen=True)
class DocRecord:
    id: str
    rel_path: str
    source_url: str
    text: str


def _sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def _read_text(path: Path) -> str:
    # Kubernetes website docs are mostly UTF-8; be tolerant.
    return path.read_text(encoding="utf-8", errors="replace")


def _normalize_newlines(s: str) -> str:
    return s.replace("\r\n", "\n").replace("\r", "\n")


def _strip_front_matter_markdown(s: str) -> str:
    # Remove common Hugo front matter:
    # ---
    # ...
    # ---
    if s.startswith("---\n"):
        m = re.search(r"\n---\n", s[4:])
        if m:
            # m.start() is offset within s[4:], so add 4 and len("\n---\n")
            end = 4 + m.start() + len("\n---\n")
            return s[end:]
    return s


def _k8s_zip_url(repo: str, ref: str) -> str:
    # Example:
    # https://github.com/kubernetes/website/archive/refs/heads/main.zip
    if ref.startswith("refs/"):
        ref = ref.replace("refs/", "", 1)
    if "/" in ref and not ref.startswith("heads/") and not ref.startswith("tags/"):
        # allow passing "heads/main" or "tags/v1.2.3"
        ref = ref
    # Heuristic: if user passed "vX.Y.Z" treat as tag; else treat as branch.
    if re.match(r"^v?\d+\.\d+(\.\d+)?", ref):
        return f"https://github.com/{repo}/archive/refs/tags/{ref}.zip"
    return f"https://github.com/{repo}/archive/refs/heads/{ref}.zip"


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)


def _iter_doc_files(
    extracted_root: Path, content_subdir: str
) -> Iterator[Tuple[Path, str]]:
    """
    Yields (absolute_path, rel_path_from_content_root).
    """
    content_root = extracted_root / content_subdir
    if not content_root.exists():
        raise FileNotFoundError(f"Expected docs path not found: {content_root}")

    for p in content_root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in {".md", ".mdx"}:
            continue
        rel = str(p.relative_to(content_root))
        yield p, rel


def _make_source_url(repo: str, ref: str, content_subdir: str, rel_path: str) -> str:
    # Best-effort, helpful for provenance.
    return f"https://github.com/{repo}/blob/{ref}/{content_subdir}/{rel_path}"


def build_records_from_zip(
    zip_path: Path,
    repo: str,
    ref: str,
    content_subdir: str,
) -> list[DocRecord]:
    with zipfile.ZipFile(zip_path, "r") as z:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            z.extractall(td_path)
            # zip has a single top-level dir like "website-main/"
            children = [p for p in td_path.iterdir() if p.is_dir()]
            if len(children) != 1:
                raise RuntimeError(f"Unexpected zip structure: {children}")
            root = children[0]

            records: list[DocRecord] = []
            for abs_path, rel_path in _iter_doc_files(root, content_subdir):
                txt = _normalize_newlines(_read_text(abs_path))
                txt = _strip_front_matter_markdown(txt)
                source_url = _make_source_url(repo, ref, content_subdir, rel_path)
                rec_id = _sha1(source_url)
                records.append(
                    DocRecord(
                        id=rec_id, rel_path=rel_path, source_url=source_url, text=txt
                    )
                )
            return records


def write_outputs(records: Iterable[DocRecord], out_dir: Path) -> Tuple[Path, Path]:
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    corpus_path = out_dir / "corpus.jsonl"
    count = 0

    with open(corpus_path, "w", encoding="utf-8") as f:
        for r in records:
            count += 1
            dst = raw_dir / r.rel_path
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(r.text, encoding="utf-8")
            f.write(
                json.dumps(
                    {
                        "id": r.id,
                        "rel_path": r.rel_path,
                        "source_url": r.source_url,
                        "text": r.text,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    if count == 0:
        raise RuntimeError(
            "No docs were collected. Check --content-subdir and filters."
        )

    return raw_dir, corpus_path


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--repo",
        default=K8S_WEBSITE_REPO,
        help="GitHub repo in owner/name form (default: kubernetes/website)",
    )
    ap.add_argument(
        "--ref",
        default=DEFAULT_REF,
        help="Git ref: branch (main) or tag (vX.Y.Z). Default: main",
    )
    ap.add_argument(
        "--content-subdir",
        default="content/en/docs",
        help="Subdir within the repo that contains docs (default: content/en/docs)",
    )
    ap.add_argument(
        "--out-dir",
        default=str(Path("datasources") / "k8s"),
        help="Output directory (default: datasources/k8s)",
    )
    args = ap.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    url = _k8s_zip_url(args.repo, args.ref)
    zip_path = out_dir / f"{args.repo.replace('/', '_')}-{args.ref}.zip"

    print(f"[k8s_fetch_docs] downloading: {url}")
    print(f"[k8s_fetch_docs] -> {zip_path}")
    _download(url, zip_path)

    print("[k8s_fetch_docs] extracting + building corpus...")
    records = build_records_from_zip(
        zip_path=zip_path,
        repo=args.repo,
        ref=args.ref,
        content_subdir=args.content_subdir,
    )

    raw_dir, corpus_path = write_outputs(records, out_dir)
    print(f"[k8s_fetch_docs] wrote {len(records)} files to {raw_dir}")
    print(f"[k8s_fetch_docs] wrote corpus to {corpus_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
