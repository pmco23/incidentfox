#!/usr/bin/env python3
"""
Ingest /datasources/k8s into RAPTOR and save a tree pickle.

Expected input: datasources/k8s/corpus.jsonl (from scripts/k8s_fetch_docs.py).

Notes:
- By default, RAPTOR uses OpenAI for embeddings + summarization + QA.
- You can reduce OpenAI cost by switching embeddings to SBERT via --embedding-model sbert.
  Summarization and QA will still use OpenAI unless you customize those models.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import traceback
from pathlib import Path
from typing import Iterable, Optional

import tiktoken
from raptor import (
    BaseEmbeddingModel,
    BaseQAModel,
    BaseSummarizationModel,
    ClusterTreeConfig,
    GPT3TurboQAModel,
    GPT3TurboSummarizationModel,
    OpenAIEmbeddingModel,
    OpenAILayeredSummarizationModel,
    RetrievalAugmentation,
    RetrievalAugmentationConfig,
    TreeRetrieverConfig,
)
from raptor.embedding_cache import CachedEmbeddingModel, EmbeddingCache
from raptor.KeywordModels import OpenAIKeywordModel, SimpleKeywordModel
from raptor.SummarizationModels import CachedSummarizationModel
from raptor.summary_cache import SummaryCache
from raptor.utils import split_markdown_semantic, split_semantic_embedding, split_text

from scripts.visualize_tree_html import build_graph_data, write_html


def _load_dotenv_if_present(dotenv_path: Path) -> None:
    """
    Minimal .env loader (avoids extra dependency).
    Only sets environment variables that are not already set.
    """
    if not dotenv_path.exists():
        return
    try:
        for line in dotenv_path.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and (k not in os.environ) and v:
                os.environ[k] = v
    except Exception:
        # Best effort; do not fail ingestion due to dotenv parsing.
        return


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


def _filter_records(
    records: Iterable[dict], *, prefix: Optional[str] = None
) -> list[dict]:
    if not prefix:
        return list(records)
    p = prefix.lstrip("/")
    out: list[dict] = []
    for r in records:
        rel = (r.get("rel_path") or "").lstrip("/")
        if rel.startswith(p):
            out.append(r)
    return out


def build_big_text(records: Iterable[dict], include_urls: bool = True) -> str:
    parts: list[str] = []
    for r in records:
        title = r.get("rel_path") or r.get("id") or "doc"
        url = r.get("source_url", "")
        text = r.get("text", "")
        if include_urls and url:
            header = f"# {title}\nSource: {url}\n\n"
        else:
            header = f"# {title}\n\n"
        parts.append(header + text.strip() + "\n\n---\n\n")
    return "".join(parts)


def build_chunks_per_doc(
    records: list[dict],
    *,
    tokenizer,
    tb_max_tokens: int,
    chunking: str,
    embedder=None,
    include_urls: bool = True,
    semantic_unit: str = "sentence",
    semantic_sim_threshold: float = 0.78,
    semantic_adaptive: bool = False,
    semantic_min_chunk_tokens: int = 120,
) -> list[str]:
    """
    Chunk each document independently so chunks never cross doc boundaries.
    Each chunk is prefixed with a short header containing rel_path + Source URL for provenance.
    """
    chunks_out: list[str] = []
    for r in records:
        title = r.get("rel_path") or r.get("id") or "doc"
        url = r.get("source_url", "")
        text = (r.get("text", "") or "").strip()
        if not text:
            continue

        if include_urls and url:
            header = f"# {title}\nSource: {url}\n\n"
        else:
            header = f"# {title}\n\n"

        if chunking == "markdown":
            pieces = split_markdown_semantic(text, tokenizer, int(tb_max_tokens))
        elif chunking == "semantic":
            if embedder is None:
                raise ValueError("semantic chunking requires embedder")
            pieces = split_semantic_embedding(
                text,
                tokenizer,
                int(tb_max_tokens),
                embedder=embedder,
                unit=semantic_unit,
                similarity_threshold=float(semantic_sim_threshold),
                adaptive_threshold=bool(semantic_adaptive),
                min_chunk_tokens=int(semantic_min_chunk_tokens),
            )
        else:
            pieces = split_text(text, tokenizer, int(tb_max_tokens))

        for p in pieces:
            p = (p or "").strip()
            if not p:
                continue
            chunks_out.append(header + p)
    return chunks_out


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--corpus",
        default=str(Path("datasources") / "k8s" / "corpus.jsonl"),
        help="Path to corpus.jsonl (default: datasources/k8s/corpus.jsonl)",
    )
    ap.add_argument(
        "--out-tree",
        default=str(Path("datasources") / "k8s" / "raptor_tree.pkl"),
        help="Where to save the RAPTOR tree pickle (default: datasources/k8s/raptor_tree.pkl)",
    )
    ap.add_argument(
        "--max-docs",
        type=int,
        default=None,
        help="Optional cap on number of docs to ingest (useful for quick tests)",
    )
    ap.add_argument(
        "--filter-prefix",
        default=None,
        help="Only ingest docs whose rel_path starts with this prefix (e.g. concepts/).",
    )
    ap.add_argument(
        "--chunk-per-doc",
        action="store_true",
        help="Chunk each document independently (prevents chunks from crossing doc boundaries). Recommended.",
    )
    ap.add_argument(
        "--smoke",
        action="store_true",
        help="Quick pipeline smoke test: defaults to --max-docs 25 and writes to datasources/k8s/raptor_tree_smoke.pkl unless --out-tree is set.",
    )
    ap.add_argument(
        "--sample-chunks",
        type=int,
        default=None,
        help=(
            "Optional cap on the number of leaf chunks (post-split) to build the tree from. "
            "This is the fastest way to validate the full pipeline on ~100 leaves."
        ),
    )
    ap.add_argument(
        "--chunking",
        choices=["simple", "markdown", "semantic"],
        default="simple",
        help=(
            "Chunking strategy. "
            "simple: legacy sentence/newline splitter (fast but can be semantically messy). "
            "markdown: structure-aware splitter using headings + code fences (recommended for docs). "
            "semantic: embedding-based topic-shift chunking (best coherence; more embedding calls)."
        ),
    )
    ap.add_argument(
        "--semantic-unit",
        choices=["sentence", "paragraph"],
        default="sentence",
        help="Semantic chunking unit granularity (default: sentence).",
    )
    ap.add_argument(
        "--semantic-sim-threshold",
        type=float,
        default=0.78,
        help="Cosine similarity cutoff for topic-shift boundaries (default: 0.78).",
    )
    ap.add_argument(
        "--semantic-adaptive",
        action="store_true",
        help="Enable adaptive thresholding based on per-doc similarity stats (recommended).",
    )
    ap.add_argument(
        "--semantic-min-chunk-tokens",
        type=int,
        default=120,
        help="Minimum tokens before allowing a semantic boundary split (default: 120).",
    )
    ap.add_argument(
        "--mode",
        choices=["openai", "offline"],
        default="offline",
        help=(
            "openai: uses RAPTOR defaults (OpenAI embedding + OpenAI summarization + OpenAI QA). "
            "offline: uses local hashing embeddings + simple summarizer/QA (no API keys, no model downloads)."
        ),
    )
    ap.add_argument(
        "--openai-api-key",
        default=None,
        help="OpenAI API key (optional; else uses env var)",
    )
    ap.add_argument(
        "--dotenv",
        default=".env",
        help="Path to .env file (default: .env). Loaded only if OPENAI_API_KEY not already set.",
    )
    ap.add_argument(
        "--openai-qa-model",
        default=None,
        help="OpenAI chat model for QA (e.g. gpt-4.1-mini). Defaults to repo default.",
    )
    ap.add_argument(
        "--openai-summarize-model",
        default=None,
        help="OpenAI chat model for summarization (e.g. gpt-4.1-mini). Defaults to repo default.",
    )
    ap.add_argument(
        "--openai-embed-model",
        default=None,
        help="OpenAI embedding model (e.g. text-embedding-3-large). Defaults to repo default.",
    )
    ap.add_argument(
        "--usage-log-path",
        default=None,
        help="Optional JSONL path to log token usage + durations for OpenAI calls (sets RAPTOR_USAGE_LOG_PATH).",
    )
    ap.add_argument(
        "--cache-embeddings",
        action="store_true",
        help="Enable persistent embedding cache (recommended for reruns).",
    )
    ap.add_argument(
        "--embedding-cache-path",
        default=str(Path("datasources") / "k8s" / ".cache" / "embeddings.sqlite"),
        help="SQLite path for embedding cache (default: datasources/k8s/.cache/embeddings.sqlite)",
    )
    ap.add_argument(
        "--embed-max-workers",
        type=int,
        default=4,
        help="Max worker threads for embedding requests (default: 4). Reduce if you hit rate limits.",
    )
    ap.add_argument(
        "--summary-max-workers",
        type=int,
        default=2,
        help="Max worker threads for summarization requests (default: 2). Increase cautiously; chat rate limits are easier to hit.",
    )
    ap.add_argument(
        "--progress",
        action="store_true",
        help="Enable progress bars / extra logging (sets RAPTOR_PROGRESS=1).",
    )
    ap.add_argument(
        "--extract-keywords",
        action="store_true",
        help="After building the tree, extract keyword lists for selected layers and store on nodes.",
    )
    ap.add_argument(
        "--keywords-min-layer",
        type=int,
        default=2,
        help="Only extract keywords for nodes at or above this layer (default: 2).",
    )
    ap.add_argument(
        "--keywords-max",
        type=int,
        default=12,
        help="Max keywords per node (default: 12).",
    )
    ap.add_argument(
        "--keywords-model",
        default=None,
        help="OpenAI model id for keyword extraction (defaults to --openai-summarize-model or gpt-5.2).",
    )
    ap.add_argument(
        "--cache-summaries",
        action="store_true",
        help="Enable persistent summary cache (recommended for reruns / incremental workflows).",
    )
    ap.add_argument(
        "--summary-cache-path",
        default=str(Path("datasources") / "k8s" / ".cache" / "summaries.sqlite"),
        help="SQLite path for summary cache (default: datasources/k8s/.cache/summaries.sqlite)",
    )
    ap.add_argument(
        "--summary-debug-log-path",
        default=None,
        help=(
            "Optional JSONL path to append raw OpenAI prompt+output when the summarizer detects "
            "extractive/copy behavior or truncation. Useful for sanity-checking by replaying direct API calls."
        ),
    )
    ap.add_argument(
        "--summary-debug-events",
        default="guard",
        help="Comma-separated events to log when --summary-debug-log-path is set: guard,truncation,all (default: guard).",
    )
    ap.add_argument(
        "--summary-debug-max-chars",
        type=int,
        default=0,
        help="Optional cap per logged message/output (0 = no cap). Only used when --summary-debug-log-path is set.",
    )
    ap.add_argument(
        "--explain-params",
        action="store_true",
        help="Print a practical parameter guide pointer and exit (see docs/parameter_recommendations.md).",
    )
    ap.add_argument(
        "--auto-tune",
        action="store_true",
        help=(
            "Apply heuristic defaults for --tb-summarization-length and --target-top-nodes based on "
            "your goal + estimated leaf count. Still fully overrideable by explicit flags."
        ),
    )
    ap.add_argument(
        "--tune-goal",
        choices=["human", "balanced", "rag"],
        default="balanced",
        help="Tuning goal used by --auto-tune (default: balanced).",
    )

    # Optional export helpers
    ap.add_argument(
        "--export-html",
        action="store_true",
        help="After saving the tree pickle, export an interactive HTML visualization next to it (or to --out-html).",
    )
    ap.add_argument(
        "--out-html",
        default=None,
        help="Optional output HTML path. Defaults to --out-tree with .html suffix.",
    )
    ap.add_argument(
        "--html-title",
        default="RAPTOR Tree",
        help="Title used for the exported HTML (default: RAPTOR Tree).",
    )
    ap.add_argument(
        "--html-max-label-chars",
        type=int,
        default=120,
        help="Max chars from node text to include in hover tooltip (default: 120).",
    )
    ap.add_argument(
        "--html-max-nodes",
        type=int,
        default=None,
        help="Optional cap on number of nodes exported to HTML (useful for huge trees).",
    )
    ap.add_argument(
        "--html-min-layer",
        type=int,
        default=None,
        help="Only include nodes at or above this layer in the exported HTML.",
    )
    ap.add_argument(
        "--html-max-layer",
        type=int,
        default=None,
        help="Only include nodes at or below this layer in the exported HTML.",
    )

    # Tree builder knobs
    ap.add_argument(
        "--tb-max-tokens", type=int, default=400, help="Chunk size (default: 400)"
    )
    ap.add_argument(
        "--tb-num-layers",
        type=int,
        default=3,
        help="Max number of tree layers to build (default: 3)",
    )
    ap.add_argument(
        "--tb-summarization-length",
        type=int,
        default=180,
        help="Target summary max_new_tokens for cluster summaries (default: 180)",
    )
    ap.add_argument(
        "--tb-summary-length-by-layer",
        default=None,
        help="Optional per-layer summary lengths, e.g. '1=200,2=120,3=80'. Overrides --tb-summarization-length for those layers.",
    )
    ap.add_argument(
        "--tb-summary-mode-by-layer",
        default=None,
        help="Optional per-layer summary mode, e.g. '1=details,2=summary,3=bullets'. Modes: details|summary|bullets|keywords.",
    )
    ap.add_argument(
        "--tb-summary-default-mode",
        default="details",
        help="Default summary mode when not specified per layer (default: details).",
    )
    ap.add_argument(
        "--tb-summary-profile",
        choices=["none", "chapter-summary", "browse", "rag"],
        default="none",
        help=(
            "Named preset for layer-aware summary settings. "
            "Applies defaults for --tb-summary-length-by-layer / --tb-summary-mode-by-layer / --tb-summary-default-mode. "
            "Explicit flags always override the profile."
        ),
    )
    ap.add_argument(
        "--auto-depth",
        action="store_true",
        help="Automatically build until top layer <= --target-top-nodes (or max layers).",
    )
    ap.add_argument(
        "--target-top-nodes",
        type=int,
        default=75,
        help="Target size for top layer when --auto-depth is enabled (default: 75).",
    )

    # Retriever knobs (primarily affects answering later)
    ap.add_argument(
        "--tr-top-k",
        type=int,
        default=12,
        help="Top-k nodes to retrieve for context (default: 12)",
    )

    # Clustering knobs (important for runtime)
    ap.add_argument(
        "--cluster-max-clusters",
        type=int,
        default=20,
        help="Cap for GMM model selection (smaller = faster). Default: 20",
    )
    ap.add_argument(
        "--cluster-threshold",
        type=float,
        default=0.1,
        help="GMM membership threshold used in clustering (default: 0.1)",
    )
    ap.add_argument(
        "--reduction-dimension",
        type=int,
        default=6,
        help="UMAP reduction dimension used during clustering (smaller = faster). Default: 6",
    )
    ap.add_argument(
        "--cluster-max-length-tokens",
        type=int,
        default=12000,
        help=(
            "Max token budget per cluster before RAPTOR reclusters it. "
            "Larger = fewer reclustering passes (faster). Default: 12000"
        ),
    )
    args = ap.parse_args(argv)

    def _parse_kv_map(s: Optional[str]) -> dict:
        if not s:
            return {}
        out = {}
        for part in str(s).split(","):
            part = part.strip()
            if not part:
                continue
            if "=" not in part:
                raise ValueError(f"Invalid mapping entry (expected k=v): {part}")
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
        return out

    def _profile_defaults(name: str) -> tuple[dict[int, int], dict[int, str], str]:
        """
        Returns (length_by_layer, mode_by_layer, default_mode).
        Layers are target layers (L1, L2, ...).
        """
        name = (name or "none").strip().lower()
        if name == "chapter-summary":
            # doc chapter -> doc summary -> bullet points/main messages (top)
            return (
                {1: 200, 2: 120, 3: 80, 4: 60},
                {1: "summary", 2: "summary", 3: "bullets", 4: "bullets"},
                "summary",
            )
        if name == "browse":
            # very human-friendly, short, strongly abstractive
            return (
                {1: 180, 2: 100, 3: 70, 4: 50},
                {1: "summary", 2: "bullets", 3: "bullets", 4: "bullets"},
                "summary",
            )
        if name == "rag":
            # richer summaries for better matching (less abstract)
            return (
                {1: 260, 2: 180, 3: 120, 4: 80},
                {1: "details", 2: "summary", 3: "summary", 4: "bullets"},
                "details",
            )
        return ({}, {}, str(args.tb_summary_default_mode))

    if args.explain_params:
        print("")
        print("[ingest_k8s] Parameter guide: docs/parameter_recommendations.md")
        print("")
        print("Common starting points:")
        print(
            "- Human browsing:   --chunking markdown --tb-summarization-length 150-200 --auto-depth --target-top-nodes 10-25"
        )
        print(
            "- Balanced:         --chunking markdown --tb-summarization-length 180-240 --auto-depth --target-top-nodes 30-60"
        )
        print(
            "- Retrieval-heavy:  --chunking semantic --tb-summarization-length 280-400 --auto-depth --target-top-nodes 50-100"
        )
        return 0

    if args.smoke:
        if args.max_docs is None:
            args.max_docs = 25
        # If user didn't explicitly set out-tree (i.e. left default), redirect to a smoke artifact.
        if args.out_tree == str(Path("datasources") / "k8s" / "raptor_tree.pkl"):
            args.out_tree = str(Path("datasources") / "k8s" / "raptor_tree_smoke.pkl")

    if args.progress:
        os.environ["RAPTOR_PROGRESS"] = "1"

    # Throttle embedding concurrency to avoid rate limits.
    os.environ["RAPTOR_EMBED_MAX_WORKERS"] = str(max(1, int(args.embed_max_workers)))
    # Throttle summarization concurrency to avoid chat rate limits.
    os.environ["RAPTOR_SUMMARY_MAX_WORKERS"] = str(
        max(1, int(args.summary_max_workers))
    )
    # Optional summarizer debug logging (raw prompt + output JSONL)
    if args.summary_debug_log_path:
        os.environ["RAPTOR_SUMMARY_DEBUG_LOG_PATH"] = str(args.summary_debug_log_path)
        os.environ["RAPTOR_SUMMARY_DEBUG_EVENTS"] = str(
            args.summary_debug_events or "guard"
        )
        os.environ["RAPTOR_SUMMARY_DEBUG_MAX_CHARS"] = str(
            int(args.summary_debug_max_chars or 0)
        )
    # Optional usage logging (tokens/durations for OpenAI calls)
    if args.usage_log_path:
        os.environ["RAPTOR_USAGE_LOG_PATH"] = str(args.usage_log_path)

    # Load .env if present and key isn't already set.
    if "OPENAI_API_KEY" not in os.environ:
        _load_dotenv_if_present(Path(args.dotenv))

    if args.openai_api_key:
        os.environ["OPENAI_API_KEY"] = args.openai_api_key

    corpus_path = Path(args.corpus)
    if not corpus_path.exists():
        raise FileNotFoundError(
            f"Corpus not found: {corpus_path}. Run scripts/k8s_fetch_docs.py first."
        )

    # Important UX: if --filter-prefix is set, apply --max-docs AFTER filtering so users don't
    # accidentally read N docs that are all outside the prefix and end up with docs=0.
    if args.filter_prefix and args.max_docs is not None:
        records = list(iter_corpus_jsonl(corpus_path, max_docs=None))
        records = _filter_records(records, prefix=args.filter_prefix)
        records = records[: int(args.max_docs)]
    else:
        records = list(iter_corpus_jsonl(corpus_path, max_docs=args.max_docs))
        records = _filter_records(records, prefix=args.filter_prefix)
    big_text = build_big_text(records, include_urls=True)
    print(
        f"[ingest_k8s] mode={args.mode} docs={len(records)} chars={len(big_text)} tb_max_tokens={args.tb_max_tokens} tb_num_layers={args.tb_num_layers}",
        flush=True,
    )

    # --- Offline-friendly models (no API keys, no model downloads) ---
    # These exist only to let you build the tree + visualize it immediately.
    # For real QA quality, switch to --mode openai or plug in stronger open-source LLMs.
    class HashingEmbeddingModel(BaseEmbeddingModel):
        def __init__(self, n_features: int = 512):
            from sklearn.feature_extraction.text import HashingVectorizer

            self.vec = HashingVectorizer(
                n_features=n_features,
                alternate_sign=False,
                norm="l2",
            )

        def create_embedding(self, text):
            v = self.vec.transform([text])
            # RAPTOR expects an array-like; return dense float list.
            return v.toarray()[0].astype("float32")

    class TruncSummarizationModel(BaseSummarizationModel):
        def summarize(self, context, max_tokens=150):
            # "Summarize" by truncating token-wise using the same cl100k tokenizer RAPTOR uses elsewhere.
            import tiktoken

            enc = tiktoken.get_encoding("cl100k_base")
            toks = enc.encode(context)
            toks = toks[:max_tokens]
            return enc.decode(toks)

    class SimpleQAModel(BaseQAModel):
        def answer_question(self, context, question):
            # Not used by this ingest script, but required to avoid OpenAI defaults.
            return context[:5000]

    embedding_model = None
    summarization_model = None
    qa_model = None

    if args.mode == "offline":
        embedding_model = HashingEmbeddingModel()
        summarization_model = TruncSummarizationModel()
        qa_model = SimpleQAModel()
    elif args.mode == "openai":
        # Optional: override OpenAI model IDs.
        embed_model_id = args.openai_embed_model or "text-embedding-ada-002"
        embedding_model = OpenAIEmbeddingModel(model=embed_model_id)
        if args.cache_embeddings:
            cache = EmbeddingCache(args.embedding_cache_path)
            embedding_model = CachedEmbeddingModel(
                embedding_model,
                cache=cache,
                model_id=embed_model_id,
            )
        # Summarization: optionally layer-aware.
        if args.openai_summarize_model:
            base_id = args.openai_summarize_model
        else:
            base_id = "gpt-3.5-turbo"

        # Apply summary profile defaults first, then merge explicit flags on top.
        prof_len, prof_mode, prof_default_mode = _profile_defaults(
            args.tb_summary_profile
        )
        if (
            args.tb_summary_profile != "none"
            and args.tb_summary_default_mode == "details"
        ):
            # Only override default_mode if the user left it at its default.
            args.tb_summary_default_mode = prof_default_mode

        mode_by_layer_raw = _parse_kv_map(args.tb_summary_mode_by_layer)
        mode_by_layer = {}
        # Start with profile
        mode_by_layer.update(prof_mode)
        # Overlay explicit
        for k, v in mode_by_layer_raw.items():
            mode_by_layer[int(k)] = str(v)

        if mode_by_layer:
            summarization_model = OpenAILayeredSummarizationModel(
                model=base_id,
                default_mode=args.tb_summary_default_mode,
                mode_by_layer=mode_by_layer,
            )
        elif args.openai_summarize_model:
            summarization_model = GPT3TurboSummarizationModel(model=base_id)

        # Optional summary cache wrapper (applies to both layered + non-layered summarizers).
        if args.cache_summaries and summarization_model is not None:
            sc = SummaryCache(args.summary_cache_path)
            # Important: incorporate a prompt/version "namespace" into model_id so
            # cache doesn't serve stale summaries when prompts change.
            prompt_sig = {
                "summarizer": type(summarization_model).__name__,
                "base_model": str(base_id),
                "default_mode": str(getattr(args, "tb_summary_default_mode", "")),
                "mode_by_layer": mode_by_layer,
                "profile": str(getattr(args, "tb_summary_profile", "")),
                "prompt_version": str(
                    getattr(summarization_model, "prompt_version", "v1")
                ),
            }
            prompt_sig_str = json.dumps(prompt_sig, sort_keys=True, ensure_ascii=False)
            prompt_hash = hashlib.sha1(
                prompt_sig_str.encode("utf-8", errors="replace")
            ).hexdigest()[:12]
            summarization_model = CachedSummarizationModel(
                summarization_model,
                cache=sc,
                model_id=f"{base_id}|{prompt_hash}",
            )
        if args.openai_qa_model:
            qa_model = GPT3TurboQAModel(model=args.openai_qa_model)

    # Build configs explicitly so we can pass clustering parameters through ClusterTreeConfig.
    length_by_layer_raw = _parse_kv_map(args.tb_summary_length_by_layer)
    summarization_length_by_layer = {}
    # Start with profile
    prof_len, _prof_mode, _prof_default = _profile_defaults(args.tb_summary_profile)
    summarization_length_by_layer.update(prof_len)
    # Overlay explicit
    for k, v in length_by_layer_raw.items():
        summarization_length_by_layer[int(k)] = int(v)

    tree_builder_config = ClusterTreeConfig(
        reduction_dimension=args.reduction_dimension,
        max_tokens=args.tb_max_tokens,
        num_layers=args.tb_num_layers,
        summarization_length=args.tb_summarization_length,
        summarization_length_by_layer=summarization_length_by_layer,
        summarization_model=summarization_model,
        embedding_models=(
            {"EMB": embedding_model} if embedding_model is not None else None
        ),
        cluster_embedding_model="EMB" if embedding_model is not None else None,
        clustering_params={
            "threshold": args.cluster_threshold,
            "max_clusters": args.cluster_max_clusters,
            "max_length_in_cluster": args.cluster_max_length_tokens,
        },
        auto_depth=args.auto_depth,
        target_top_nodes=args.target_top_nodes,
        max_layers=args.tb_num_layers,
    )

    tree_retriever_config = TreeRetrieverConfig(
        top_k=args.tr_top_k,
        context_embedding_model="EMB" if embedding_model is not None else "OpenAI",
        embedding_model=embedding_model,
    )

    cfg = RetrievalAugmentationConfig(
        tree_builder_config=tree_builder_config,
        tree_retriever_config=tree_retriever_config,
        qa_model=qa_model,
        tree_builder_type="cluster",
    )

    ra = RetrievalAugmentation(config=cfg)
    t0 = time.time()
    try:
        # Heuristic tuning pass (safe defaults). This is intentionally conservative and transparent.
        if args.auto_tune:
            enc = tree_builder_config.tokenizer or tiktoken.get_encoding("cl100k_base")
            approx_tokens = len(enc.encode(big_text))
            approx_leaf = max(
                1, int((approx_tokens / max(1, int(args.tb_max_tokens))) + 0.999)
            )

            goal = (args.tune_goal or "balanced").strip().lower()
            if goal == "human":
                tuned_summary = max(120, min(200, int(int(args.tb_max_tokens) * 0.22)))
                tuned_top = max(10, min(25, int(round(approx_leaf**0.5))))
            elif goal == "rag":
                tuned_summary = max(250, min(400, int(int(args.tb_max_tokens) * 0.35)))
                tuned_top = max(
                    50, min(100, int(round(max(50.0, approx_leaf**0.5 * 4.0))))
                )
            else:  # balanced
                tuned_summary = max(180, min(240, int(int(args.tb_max_tokens) * 0.28)))
                tuned_top = max(
                    30, min(60, int(round(max(30.0, approx_leaf**0.5 * 3.0))))
                )

            # Apply only when values look like defaults (to respect explicit user choices).
            if int(args.tb_summarization_length) == 180:
                args.tb_summarization_length = int(tuned_summary)
                tree_builder_config.summarization_length = int(tuned_summary)
            if int(args.target_top_nodes) == 75:
                args.target_top_nodes = int(tuned_top)
                tree_builder_config.target_top_nodes = int(tuned_top)

            if not args.auto_depth:
                args.auto_depth = True
                tree_builder_config.auto_depth = True

            print(
                f"[ingest_k8s] auto_tune(goal={goal}) approx_leaf={approx_leaf} "
                f"tb_summarization_length={args.tb_summarization_length} target_top_nodes={args.target_top_nodes} auto_depth={args.auto_depth}",
                flush=True,
            )

        # Warnings to help users understand “why this might look odd”.
        if (
            args.mode == "openai"
            and args.chunking == "semantic"
            and not args.cache_embeddings
        ):
            print(
                "[ingest_k8s] WARNING: --chunking semantic in openai mode can be expensive (extra embeddings). "
                "Consider --cache-embeddings.",
                flush=True,
            )
        if int(args.tb_summarization_length) >= int(int(args.tb_max_tokens) * 0.35):
            print(
                "[ingest_k8s] WARNING: tb_summarization_length is relatively high vs tb_max_tokens; "
                "higher-layer nodes may look less like summaries to humans.",
                flush=True,
            )

        # Configure chunker for full builds (TreeBuilder.build_from_text).
        if args.chunking == "markdown":
            tree_builder_config.chunker = split_markdown_semantic
        elif args.chunking == "semantic":
            # Capture the embedder used for leaf embeddings (prefer cached OpenAI embedder in openai mode).
            if embedding_model is None:
                raise ValueError("--chunking semantic requires an embedding model")

            def _chunker(text, tokenizer, max_tokens):
                return split_semantic_embedding(
                    text,
                    tokenizer,
                    int(max_tokens),
                    embedder=embedding_model,
                    unit=args.semantic_unit,
                    similarity_threshold=float(args.semantic_sim_threshold),
                    adaptive_threshold=bool(args.semantic_adaptive),
                    min_chunk_tokens=int(args.semantic_min_chunk_tokens),
                )

            tree_builder_config.chunker = _chunker

        if args.sample_chunks is not None or args.chunk_per_doc:
            n = int(args.sample_chunks) if args.sample_chunks is not None else None
            if n is not None and n < 1:
                raise ValueError("--sample-chunks must be >= 1")
            # Use the same tokenizer+max_tokens as the builder would.
            tokenizer = tree_builder_config.tokenizer or tiktoken.get_encoding(
                "cl100k_base"
            )
            if args.chunk_per_doc:
                chunks = build_chunks_per_doc(
                    records,
                    tokenizer=tokenizer,
                    tb_max_tokens=int(args.tb_max_tokens),
                    chunking=args.chunking,
                    embedder=embedding_model,
                    include_urls=True,
                    semantic_unit=args.semantic_unit,
                    semantic_sim_threshold=float(args.semantic_sim_threshold),
                    semantic_adaptive=bool(args.semantic_adaptive),
                    semantic_min_chunk_tokens=int(args.semantic_min_chunk_tokens),
                )
            else:
                if args.chunking == "markdown":
                    chunks = split_markdown_semantic(
                        big_text, tokenizer, int(args.tb_max_tokens)
                    )
                elif args.chunking == "semantic":
                    if embedding_model is None:
                        raise ValueError(
                            "--chunking semantic requires an embedding model"
                        )
                    chunks = split_semantic_embedding(
                        big_text,
                        tokenizer,
                        int(args.tb_max_tokens),
                        embedder=embedding_model,
                        unit=args.semantic_unit,
                        similarity_threshold=float(args.semantic_sim_threshold),
                        adaptive_threshold=bool(args.semantic_adaptive),
                        min_chunk_tokens=int(args.semantic_min_chunk_tokens),
                    )
                else:
                    chunks = split_text(big_text, tokenizer, int(args.tb_max_tokens))

            if n is not None and len(chunks) > n:
                chunks = chunks[:n]
            print(
                f"[ingest_k8s] sample_chunks={n} actual_leaf_chunks={len(chunks)}",
                flush=True,
            )
            ra.add_chunks(chunks)
        else:
            ra.add_documents(big_text)

        # Optional post-pass: extract keywords per node (useful for keyword search / knowledge-graph edges).
        if args.extract_keywords and ra.tree is not None:
            min_layer = int(args.keywords_min_layer)
            max_kw = max(1, int(args.keywords_max))
            if args.mode == "openai":
                km = OpenAIKeywordModel(
                    model=(
                        args.keywords_model or args.openai_summarize_model or "gpt-5.2"
                    )
                )
            else:
                km = SimpleKeywordModel()

            # Extract for selected layers only to keep cost sane.
            total = 0
            for layer, nodes in sorted(ra.tree.layer_to_nodes.items()):
                if int(layer) < min_layer:
                    continue
                for n in nodes:
                    try:
                        txt = (getattr(n, "text", "") or "").strip()
                        n.keywords = km.extract_keywords(txt, max_keywords=max_kw)
                        total += 1
                    except Exception:
                        # Best-effort; don't fail the build for keyword extraction.
                        n.keywords = []
            print(
                f"[ingest_k8s] extracted keywords for nodes: {total} (min_layer={min_layer})",
                flush=True,
            )
    except Exception:
        print("[ingest_k8s] ERROR: add_documents failed. Traceback:", flush=True)
        traceback.print_exc()
        return 2
    finally:
        print(f"[ingest_k8s] build_seconds={time.time() - t0:.2f}", flush=True)

    out_tree = Path(args.out_tree)
    out_tree.parent.mkdir(parents=True, exist_ok=True)
    ra.save(str(out_tree))
    print(f"[ingest_k8s] saved tree: {out_tree}")

    if args.export_html and ra.tree is not None:
        out_html = (
            Path(args.out_html) if args.out_html else out_tree.with_suffix(".html")
        )
        out_html.parent.mkdir(parents=True, exist_ok=True)
        try:
            nodes, edges = build_graph_data(
                ra.tree,
                max_label_chars=int(args.html_max_label_chars),
                min_layer=args.html_min_layer,
                max_layer=args.html_max_layer,
                max_nodes=args.html_max_nodes,
            )
            write_html(
                out_html, nodes, edges, title=str(args.html_title or "RAPTOR Tree")
            )
            print(f"[ingest_k8s] exported html: {out_html}", flush=True)
        except Exception:
            print("[ingest_k8s] WARNING: failed to export HTML. Traceback:", flush=True)
            traceback.print_exc()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
