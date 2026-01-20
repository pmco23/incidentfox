#!/usr/bin/env python3
"""
CLI script to merge multiple RAPTOR trees into one.

Usage:
    python scripts/merge_trees.py tree1.pkl tree2.pkl tree3.pkl -o merged.pkl
    python scripts/merge_trees.py tree1.pkl tree2.pkl --no-rebuild -o merged.pkl

Options:
    --rebuild / --no-rebuild : Whether to rebuild upper layers (default: rebuild)
    --output, -o : Output path for merged tree
    --openai-embed-model : Embedding model for rebuild (default: text-embedding-3-small)
    --openai-summarize-model : Summarization model for rebuild (default: gpt-3.5-turbo)
"""

import argparse
import os
import pickle
import sys
from pathlib import Path

# Ensure raptor module is importable
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(REPO_ROOT))

from raptor.tree_merge import merge_trees
from raptor.tree_structures import Tree


def main():
    parser = argparse.ArgumentParser(description="Merge multiple RAPTOR trees")
    parser.add_argument("trees", nargs="+", help="Paths to tree pickle files to merge")
    parser.add_argument(
        "-o", "--output", required=True, help="Output path for merged tree"
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        default=True,
        help="Rebuild upper layers after merging (default)",
    )
    parser.add_argument(
        "--no-rebuild",
        dest="rebuild",
        action="store_false",
        help="Don't rebuild - just concatenate layers",
    )
    parser.add_argument(
        "--openai-embed-model",
        default="text-embedding-3-small",
        help="OpenAI embedding model for rebuild",
    )
    parser.add_argument(
        "--openai-summarize-model",
        default="gpt-3.5-turbo",
        help="OpenAI summarization model for rebuild",
    )
    parser.add_argument("--dotenv", default=".env", help="Path to .env file")

    args = parser.parse_args()

    # Load .env if present
    dotenv_path = Path(args.dotenv)
    if dotenv_path.exists():
        for line in dotenv_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())

    # Load all trees
    print(f"Loading {len(args.trees)} trees...")
    trees = []
    for path in args.trees:
        with open(path, "rb") as f:
            tree = pickle.load(f)
            if not isinstance(tree, Tree):
                print(f"Error: {path} does not contain a Tree object")
                return 1
            trees.append(tree)
            print(
                f"  - {path}: {len(tree.all_nodes)} nodes, {len(tree.leaf_nodes)} leaves"
            )

    # Setup builder if rebuild is requested
    builder = None
    if args.rebuild:
        from raptor.cluster_tree_builder import ClusterTreeBuilder, ClusterTreeConfig
        from raptor.EmbeddingModels import OpenAIEmbeddingModel
        from raptor.SummarizationModels import GPT3TurboSummarizationModel

        print(
            f"Setting up builder with {args.openai_embed_model} and {args.openai_summarize_model}..."
        )

        embed_model = OpenAIEmbeddingModel(model=args.openai_embed_model)
        summarize_model = GPT3TurboSummarizationModel(model=args.openai_summarize_model)

        config = ClusterTreeConfig(
            embedding_models={"EMB": embed_model},
            cluster_embedding_model="EMB",
            summarization_model=summarize_model,
        )
        builder = ClusterTreeBuilder(config)

    # Merge
    print("Merging trees...")
    merged = merge_trees(trees, rebuild_upper_layers=args.rebuild, builder=builder)

    # Save
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        pickle.dump(merged, f)

    print(f"\nMerged tree saved to {output_path}")
    print(f"  Total nodes: {len(merged.all_nodes)}")
    print(f"  Leaf nodes: {len(merged.leaf_nodes)}")
    print(f"  Root nodes: {len(merged.root_nodes)}")
    print(f"  Layers: {len(merged.layer_to_nodes)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
