#!/usr/bin/env python3
"""
Multimodal ingestion CLI tool.

Ingest content from various sources (web, files, APIs) with multimodal processing
(image, audio, video) and build RAPTOR trees.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion import IngestionOrchestrator
from raptor import RetrievalAugmentation, RetrievalAugmentationConfig


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Ingest multimodal content and build RAPTOR tree"
    )
    ap.add_argument(
        "sources",
        nargs="+",
        help="Source URLs, file paths, or API endpoints to ingest",
    )
    ap.add_argument(
        "--output-corpus",
        type=Path,
        help="Output corpus JSONL file (default: datasources/ingested/corpus.jsonl)",
    )
    ap.add_argument(
        "--output-tree",
        type=Path,
        help="Output RAPTOR tree pickle file (optional)",
    )
    ap.add_argument(
        "--openai-api-key",
        default=os.environ.get("OPENAI_API_KEY"),
        help="OpenAI API key (default: OPENAI_API_KEY env var)",
    )
    ap.add_argument(
        "--no-multimodal",
        action="store_true",
        help="Disable multimodal processing (images, audio, video)",
    )
    ap.add_argument(
        "--storage-dir",
        type=Path,
        default=Path("datasources/ingested/storage"),
        help="Directory for storing extracted assets",
    )

    # RAPTOR tree building options
    ap.add_argument(
        "--build-tree",
        action="store_true",
        help="Build RAPTOR tree after ingestion",
    )
    ap.add_argument(
        "--tb-max-tokens",
        type=int,
        default=800,
        help="Tree builder max tokens per chunk",
    )
    ap.add_argument(
        "--tb-num-layers",
        type=int,
        default=6,
        help="Tree builder number of layers",
    )

    args = ap.parse_args(argv)

    if not args.openai_api_key and not args.no_multimodal:
        print("Error: OPENAI_API_KEY required for multimodal processing")
        print("Set OPENAI_API_KEY environment variable or use --openai-api-key")
        return 1

    # Initialize orchestrator
    orchestrator = IngestionOrchestrator(
        openai_api_key=args.openai_api_key,
        enable_multimodal=not args.no_multimodal,
        storage_dir=args.storage_dir,
    )

    # Ingest sources
    print(f"Ingesting {len(args.sources)} source(s)...")
    try:
        contents = orchestrator.ingest_batch(args.sources)
        print(f"Successfully ingested {len(contents)} source(s)")
    except Exception as e:
        print(f"Error during ingestion: {e}", file=sys.stderr)
        return 1

    # Write corpus
    output_corpus = args.output_corpus or Path("datasources/ingested/corpus.jsonl")
    output_corpus.parent.mkdir(parents=True, exist_ok=True)

    print(f"Writing corpus to {output_corpus}...")
    orchestrator.ingest_to_corpus(args.sources, output_corpus)

    # Build tree if requested
    if args.build_tree or args.output_tree:
        output_tree = args.output_tree or Path("datasources/ingested/raptor_tree.pkl")
        print(f"Building RAPTOR tree to {output_tree}...")

        try:
            from raptor import (
                ClusterTreeConfig,
                OpenAIEmbeddingModel,
                TreeRetrieverConfig,
            )

            embed = OpenAIEmbeddingModel(model="text-embedding-3-large")
            tb_cfg = ClusterTreeConfig(
                max_tokens=args.tb_max_tokens,
                num_layers=args.tb_num_layers,
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
                max_layers=args.tb_num_layers,
            )

            tr_cfg = TreeRetrieverConfig(
                top_k=12,
                context_embedding_model="EMB",
                embedding_model=embed,
            )

            cfg = RetrievalAugmentationConfig(
                tree_builder_config=tb_cfg,
                tree_retriever_config=tr_cfg,
                qa_model=None,  # No QA model for ingestion
                tree_builder_type="cluster",
            )

            ra = RetrievalAugmentation(config=cfg)

            # Read corpus and build tree
            chunks = []
            with open(output_corpus, "r", encoding="utf-8") as f:
                for line in f:
                    record = json.loads(line)
                    chunks.append(record["text"])

            ra.add_chunks(chunks)
            ra.save(str(output_tree))
            print(f"Tree saved to {output_tree}")

        except Exception as e:
            print(f"Error building tree: {e}", file=sys.stderr)
            import traceback

            traceback.print_exc()
            return 1

    # Print summary
    total_cost = sum(c.metadata.processing_cost_usd or 0.0 for c in contents)
    print("\nIngestion complete!")
    print(f"  Sources: {len(contents)}")
    print(f"  Total processing cost: ${total_cost:.4f}")
    print(f"  Corpus: {output_corpus}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
