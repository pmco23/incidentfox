#!/usr/bin/env python3
"""
Ask questions against a saved RAPTOR tree (pickle).

This is a CLI (not the visualization UI). The HTML graph is for browsing; use this for QA.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Optional

import tiktoken
from openai import OpenAI
from raptor import (
    ClusterTreeConfig,
    GPT3TurboQAModel,
    OpenAIEmbeddingModel,
    RetrievalAugmentation,
    RetrievalAugmentationConfig,
    TreeRetrieverConfig,
)
from raptor.embedding_cache import CachedEmbeddingModel, EmbeddingCache

from scripts.qa_presets import PRESETS, list_presets


def _load_dotenv_if_present(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return
    for line in dotenv_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and (k not in os.environ) and v:
            os.environ[k] = v


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", required=True, help="Path to RAPTOR tree pickle")
    ap.add_argument(
        "--q", "--question", dest="question", default=None, help="Question text"
    )
    ap.add_argument(
        "--preset",
        default=None,
        help=f"Run a named preset: {', '.join(list_presets())}",
    )
    ap.add_argument(
        "--list-presets", action="store_true", help="List available presets and exit"
    )
    ap.add_argument(
        "--dotenv", default=".env", help="Optional .env file path (default: .env)"
    )

    # Retrieval knobs
    ap.add_argument(
        "--top-k", type=int, default=12, help="Retriever top-k (default: 12)"
    )
    ap.add_argument(
        "--max-context-tokens",
        type=int,
        default=2500,
        help="Retriever context token budget (default: 2500). Increase to avoid losing evidence during retrieval.",
    )

    # Optional: retrieve big then compress down before QA
    ap.add_argument(
        "--compress-context",
        choices=["none", "extractive", "llm"],
        default="none",
        help="If retrieved context exceeds --qa-max-context-tokens, compress it (default: none).",
    )
    ap.add_argument(
        "--qa-max-context-tokens",
        type=int,
        default=3500,
        help="Max context tokens passed to the QA model after optional compression (default: 3500).",
    )
    ap.add_argument(
        "--compress-chunk-tokens",
        type=int,
        default=2500,
        help="Chunk size (tokens) for context compression map step (default: 2500).",
    )
    ap.add_argument(
        "--compress-max-completion-tokens",
        type=int,
        default=450,
        help="Max output tokens per compression call (default: 450).",
    )

    # OpenAI models
    ap.add_argument(
        "--openai-embed-model",
        default="text-embedding-3-large",
        help="Embedding model id",
    )
    ap.add_argument("--openai-qa-model", default="gpt-5.2", help="QA chat model id")
    ap.add_argument(
        "--openai-compress-model",
        default=None,
        help="Optional chat model for compression (defaults to --openai-qa-model).",
    )

    # Cache
    ap.add_argument(
        "--cache-embeddings", action="store_true", help="Enable embedding cache"
    )
    ap.add_argument(
        "--embedding-cache-path",
        default=str(Path("datasources") / "k8s" / ".cache" / "embeddings.sqlite"),
        help="SQLite embedding cache path",
    )

    # Output control
    ap.add_argument(
        "--print-context",
        action="store_true",
        help="Print retrieved context before the answer",
    )
    ap.add_argument(
        "--print-citations",
        action="store_true",
        help="Print best-effort citations (source_url/original_content_ref) for selected nodes.",
    )
    ap.add_argument(
        "--print-citations",
        action="store_true",
        help="Print best-effort citations (source_url/original_content_ref) for selected nodes.",
    )
    ap.add_argument(
        "--print-nodes",
        action="store_true",
        help="Print the exact nodes selected for context (id/layer/tokens/score/snippet).",
    )
    ap.add_argument(
        "--print-nodes-max-chars",
        type=int,
        default=240,
        help="Max characters of node text to print per node (default: 240).",
    )
    ap.add_argument(
        "--json-out",
        default=None,
        help="Optional path to write JSON results (useful for benchmarks).",
    )
    ap.add_argument(
        "--no-qa",
        action="store_true",
        help="Retrieval-only: do not call the QA model (no chat LLM call)",
    )

    args = ap.parse_args(argv)

    if args.list_presets:
        for name in list_presets():
            print(name)
        return 0

    if "OPENAI_API_KEY" not in os.environ:
        _load_dotenv_if_present(Path(args.dotenv))

    if not args.question and not args.preset:
        raise SystemExit(
            "Provide either --question/--q or --preset (or use --list-presets)."
        )

    embed = OpenAIEmbeddingModel(model=args.openai_embed_model)
    if args.cache_embeddings:
        embed = CachedEmbeddingModel(
            embed,
            cache=EmbeddingCache(args.embedding_cache_path),
            model_id=args.openai_embed_model,
        )

    qa = None if args.no_qa else GPT3TurboQAModel(model=args.openai_qa_model)
    compress_model = args.openai_compress_model or args.openai_qa_model
    tokenizer = tiktoken.get_encoding("cl100k_base")

    def _count_tokens(s: str) -> int:
        try:
            return len(tokenizer.encode(s or ""))
        except Exception:
            return len((s or "").split())

    def _split_into_token_chunks(text: str, max_tokens: int) -> list[str]:
        # Split on blank lines (paragraph-ish). Then pack into token-bounded chunks.
        parts = [p.strip() for p in (text or "").split("\n\n") if p.strip()]
        chunks: list[str] = []
        cur: list[str] = []
        cur_toks = 0
        for p in parts:
            pt = _count_tokens(p)
            # If a single paragraph is huge, hard-split by tokens.
            if pt > max_tokens:
                # flush current
                if cur:
                    chunks.append("\n\n".join(cur).strip())
                    cur, cur_toks = [], 0
                toks = tokenizer.encode(p)
                for i in range(0, len(toks), max_tokens):
                    chunks.append(tokenizer.decode(toks[i : i + max_tokens]).strip())
                continue
            if cur_toks + pt > max_tokens and cur:
                chunks.append("\n\n".join(cur).strip())
                cur, cur_toks = [], 0
            cur.append(p)
            cur_toks += pt
        if cur:
            chunks.append("\n\n".join(cur).strip())
        return [c for c in chunks if c]

    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        # Pure-Python cosine similarity to avoid extra deps here.
        if not a or not b:
            return 0.0
        n = min(len(a), len(b))
        dot = 0.0
        na = 0.0
        nb = 0.0
        for i in range(n):
            x = float(a[i])
            y = float(b[i])
            dot += x * y
            na += x * x
            nb += y * y
        if na <= 0.0 or nb <= 0.0:
            return 0.0
        return float(dot / ((na**0.5) * (nb**0.5)))

    _STOPWORDS = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "to",
        "of",
        "in",
        "on",
        "for",
        "with",
        "by",
        "from",
        "is",
        "are",
        "was",
        "were",
        "be",
        "as",
        "it",
        "this",
        "that",
        "these",
        "those",
        "vs",
        "between",
        "different",
        "difference",
        "explain",
        "compare",
        "what",
        "when",
        "why",
        "how",
        "use",
        "used",
    }

    def _extractive_compress(question: str, text: str, target_tokens: int) -> str:
        # Very cheap compressor: pick the most question-relevant paragraphs until budget is filled.
        q_terms = [
            t.strip("`'\".,:;!?()[]{}").lower()
            for t in (question or "").replace("/", " ").replace("-", " ").split()
        ]
        q_terms = [t for t in q_terms if len(t) >= 3 and t not in _STOPWORDS]
        q_set = set(q_terms)

        paras = [p.strip() for p in (text or "").split("\n\n") if p.strip()]
        scored = []
        for i, p in enumerate(paras):
            pl = p.lower()
            score = sum(1 for qt in q_set if qt in pl)
            scored.append((score, i, p))
        # Prefer higher score; keep stable by original order for ties
        scored.sort(key=lambda x: (-x[0], x[1]))

        picked_idx = set()
        total = 0
        for score, i, p in scored:
            if score <= 0:
                break
            pt = _count_tokens(p)
            if total + pt > target_tokens:
                continue
            picked_idx.add(i)
            total += pt
            if total >= target_tokens:
                break

        # If nothing matched, just hard-truncate to budget.
        if not picked_idx:
            toks = tokenizer.encode(text or "")
            return tokenizer.decode(toks[:target_tokens]).strip()

        kept = [paras[i] for i in range(len(paras)) if i in picked_idx]
        out = "\n\n".join(kept).strip()
        if _count_tokens(out) <= target_tokens:
            return out
        toks = tokenizer.encode(out)
        return tokenizer.decode(toks[:target_tokens]).strip()

    def _llm_compress(question: str, text: str, target_tokens: int) -> str:
        # Safer map-reduce:
        # 1) Extractive pre-filter to reduce obvious noise while keeping verbatim key terms.
        # 2) LLM compress the pre-filtered evidence into concise bullets.
        # 3) Fallback to extractive if the LLM output looks unhelpful.
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        prefilter_tokens = int(
            min(max(target_tokens * 4, 4000), max(4000, _count_tokens(text)))
        )
        prefiltered = _extractive_compress(question, text, prefilter_tokens)

        def one_pass(src: str, *, max_out_tokens: int) -> str:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are an evidence compressor. Given (possibly long) context excerpts and a question, "
                        "extract ONLY the information relevant to answering the question. "
                        "Return bullet points (5–12) with short, factual statements. "
                        "Do NOT say you don't know; do NOT add facts not present in the context. "
                        "Preserve important technical terms verbatim when they appear in the context "
                        "(e.g., 'ClusterIP', 'NodePort', 'LoadBalancer', 'PersistentVolumeClaim', 'node affinity'). "
                        "Prefer including key terms from the question when the context supports it."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Question:\n{question}\n\nContext:\n{src}\n\nCompressed evidence bullets:",
                },
            ]
            try:
                resp = client.chat.completions.create(
                    model=compress_model,
                    messages=messages,
                    temperature=0,
                    max_completion_tokens=max_out_tokens,
                )
            except Exception as e:
                msg = str(e)
                if "Unsupported parameter" in msg and "max_tokens" in msg:
                    resp = client.chat.completions.create(
                        model=compress_model,
                        messages=messages,
                        temperature=0,
                        max_tokens=max_out_tokens,
                    )
                else:
                    raise
            content = getattr(resp.choices[0].message, "content", "") or ""
            return content.strip()

        chunks = _split_into_token_chunks(prefiltered, int(args.compress_chunk_tokens))
        if not chunks:
            return (prefiltered or text or "").strip()

        per_chunk = int(
            min(
                int(args.compress_max_completion_tokens),
                max(180, min(420, int((target_tokens * 1.2) // max(1, len(chunks))))),
            )
        )
        compressed_parts = [one_pass(c, max_out_tokens=per_chunk) for c in chunks]
        combined = "\n".join([p for p in compressed_parts if p]).strip()
        if combined and _count_tokens(combined) <= target_tokens:
            return combined

        # Reduce pass
        reduced = one_pass(
            combined,
            max_out_tokens=int(
                min(
                    int(args.compress_max_completion_tokens),
                    max(240, min(900, target_tokens)),
                )
            ),
        )
        if reduced and _count_tokens(reduced) <= target_tokens:
            # Basic sanity: if we lost all "query anchor terms", fall back to extractive.
            q_terms = [
                t.strip("`'\".,:;!?()[]{}").lower()
                for t in (question or "").replace("/", " ").replace("-", " ").split()
            ]
            q_terms = [t for t in q_terms if len(t) >= 3 and t not in _STOPWORDS]
            anchor_terms = q_terms[:8]
            if anchor_terms and not any(at in reduced.lower() for at in anchor_terms):
                toks = tokenizer.encode(prefiltered or "")
                return tokenizer.decode(toks[:target_tokens]).strip()
            return reduced

        toks = tokenizer.encode(reduced)
        out = tokenizer.decode(toks[:target_tokens]).strip()
        return (
            out
            or tokenizer.decode(
                tokenizer.encode(prefiltered or "")[:target_tokens]
            ).strip()
        )

    # TreeBuilderConfig is required by RetrievalAugmentationConfig, but we won't rebuild the tree.
    # We still pass embedding_models so retrieval can embed the query.
    tb_cfg = ClusterTreeConfig(
        max_tokens=800,
        num_layers=6,
        summarization_length=180,
        summarization_model=None,
        embedding_models={"EMB": embed},
        cluster_embedding_model="EMB",
        clustering_params={
            "threshold": 0.1,
            "max_clusters": 8,
            "max_length_in_cluster": 8000,
        },
        auto_depth=True,
        target_top_nodes=50,
        max_layers=6,
    )

    tr_cfg = TreeRetrieverConfig(
        top_k=int(args.top_k),
        context_embedding_model="EMB",
        embedding_model=embed,
    )

    cfg = RetrievalAugmentationConfig(
        tree_builder_config=tb_cfg,
        tree_retriever_config=tr_cfg,
        qa_model=qa,
        tree_builder_type="cluster",
    )

    ra = RetrievalAugmentation(config=cfg, tree=args.tree)

    def run_one(
        question: str, *, expected_contains=None, should_answer: Optional[bool] = None
    ):
        from raptor.utils import get_text_with_citations

        context, layer_info = ra.retrieve(
            question,
            top_k=int(args.top_k),
            max_tokens=int(args.max_context_tokens),
            return_layer_information=True,
        )

        # Build citation-labeled context for QA
        nodes = []
        for info in layer_info:
            idx = int(info["node_index"])
            node = ra.tree.all_nodes.get(idx)
            if node:
                nodes.append(node)

        if nodes:
            context, indexed_citations = get_text_with_citations(nodes)
            # Convert indexed citations to the output format
            citations_out = [
                {
                    "node_id": c["node_ids"][0] if c["node_ids"] else None,
                    "source": c["source"],
                    "rel_path": c.get("rel_path"),
                    "index": c["index"],
                }
                for c in indexed_citations
            ]
        else:
            indexed_citations = []
            citations_out = []

        if args.print_nodes:
            # Print selected nodes with similarity scores for debugging
            try:
                q_emb = embed.create_embedding(question)
            except Exception:
                q_emb = None

            print("\n=== Selected nodes (in order) ===\n")
            for rank, info in enumerate(layer_info, start=1):
                idx = int(info["node_index"])
                layer = int(info["layer_number"])
                node = ra.tree.all_nodes.get(idx)
                if node is None:
                    continue
                toks = _count_tokens(node.text)
                snippet = " ".join((node.text or "").splitlines()).strip()
                snippet = snippet[: int(args.print_nodes_max_chars)]
                kws = getattr(node, "keywords", None) or []
                score = None
                if q_emb is not None:
                    try:
                        n_emb = node.embeddings.get("EMB")
                        if isinstance(n_emb, list) and n_emb:
                            score = _cosine_similarity(q_emb, n_emb)
                    except Exception:
                        score = None

                score_s = "" if score is None else f" score={score:.4f}"
                kw_s = "" if not kws else f" keywords={kws}"
                print(
                    f"[{rank}] id={idx} layer={layer} tokens={toks}{score_s}{kw_s}\n  {snippet}\n"
                )
            print("=== End selected nodes ===\n")

        if args.print_citations and citations_out:
            print("\n=== Citations ===")
            for c in citations_out:
                idx = c.get("index", "?")
                src = c.get("source", "unknown")
                rel = c.get("rel_path")
                if rel:
                    print(f"[{idx}] {src} ({rel})")
                else:
                    print(f"[{idx}] {src}")
            print("=== End citations ===\n")

        # Optional: compress retrieved context down before QA so we can retrieve "big" without failing QA context limits.
        if not args.no_qa and args.compress_context != "none":
            ct = _count_tokens(context)
            if ct > int(args.qa_max_context_tokens):
                if args.compress_context == "extractive":
                    context = _extractive_compress(
                        question, context, int(args.qa_max_context_tokens)
                    )
                elif args.compress_context == "llm":
                    context = _llm_compress(
                        question, context, int(args.qa_max_context_tokens)
                    )

        if args.print_context:
            print("\n=== Retrieved context ===\n")
            print(context)
            print("\n=== End context ===\n")

        if args.no_qa:
            print("[ask_tree] (no-qa) retrieval completed.")
            return {
                "question": question,
                "answer": None,
                "ok": True,
                "should_answer": should_answer,
                "expected_contains": expected_contains,
                "citations": citations_out,
            }

        assert qa is not None
        ans = qa.answer_question(context, question, max_tokens=500)
        print(ans)

        # Simple, best-effort check.
        ok = True
        if expected_contains:
            ans_l = (ans or "").lower()
            ok = all(str(x).lower() in ans_l for x in expected_contains)
            if not ok:
                print(f"[ask_tree] FAIL expected_contains={expected_contains}")
                ok = False
        if should_answer is False:
            # For out-of-domain, our QA prompt standardizes on "I don't know based on the provided context."
            if "don't know" not in (ans or "").lower():
                print("[ask_tree] FAIL expected an 'I don't know' style answer")
                ok = False

        return {
            "question": question,
            "answer": ans,
            "ok": bool(ok),
            "should_answer": should_answer,
            "expected_contains": expected_contains,
            "citations": citations_out,
        }

    if args.preset:
        name = str(args.preset).strip()
        if name not in PRESETS:
            raise SystemExit(f"Unknown preset '{name}'. Use --list-presets.")
        rc = 0
        results = {"preset": name, "cases": []}
        print(f"[ask_tree] running preset: {name} (cases={len(PRESETS[name])})")
        for case in PRESETS[name]:
            print("\n" + "=" * 80)
            print(f"[{case.id}] {case.question}")
            r = run_one(
                case.question,
                expected_contains=case.expected_contains,
                should_answer=case.should_answer,
            )
            results["cases"].append({"id": case.id, **r})
            rc = max(rc, 0 if r.get("ok") else 2)

        if args.json_out:
            Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.json_out).write_text(
                json.dumps(results, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        return rc

    # Single question mode
    q = str(args.question)
    r = run_one(q)
    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(
            json.dumps(r, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return 0 if r.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
