#!/usr/bin/env python3
"""
Compare the original tree structure with the current one.
"""

import pickle
import subprocess
from pathlib import Path

S3_BUCKET = "raptor-kb-trees-103002841599"
TREE_NAME = "mega_ultra_v2"

# Version IDs from S3
ORIGINAL_VERSION = "9Jwi23uNj369xQMlVbQA_T1ilnjew.QM"  # Jan 10 - original
CURRENT_VERSION = "htpZVv6TOKWmYJ6OeV7KGfQbuWw9k6CF"  # Jan 19 - current


def download_version(version_id: str, local_path: str) -> None:
    subprocess.run(
        [
            "aws",
            "s3api",
            "get-object",
            "--bucket",
            S3_BUCKET,
            "--key",
            f"trees/{TREE_NAME}/{TREE_NAME}.pkl",
            "--version-id",
            version_id,
            local_path,
        ],
        check=True,
    )


def analyze_tree(tree, label: str):
    print(f"\n{'=' * 70}")
    print(f"{label}")
    print("=" * 70)
    print(f"tree.num_layers: {getattr(tree, 'num_layers', 'NOT SET')}")
    print(f"Total nodes in all_nodes: {len(tree.all_nodes)}")
    print(f"Leaf nodes: {len(tree.leaf_nodes)}")

    if hasattr(tree, "root_nodes"):
        if isinstance(tree.root_nodes, dict):
            print(f"Root nodes: {len(tree.root_nodes)}")
        elif isinstance(tree.root_nodes, list):
            print(f"Root nodes: {len(tree.root_nodes)}")

    print("\nLayer structure:")
    for layer, nodes in sorted(tree.layer_to_nodes.items()):
        print(f"  Layer {layer}: {len(nodes)} nodes")

    # Check embedding dimensions in first few nodes
    sample_dims = []
    for idx, node in list(tree.all_nodes.items())[:5]:
        if hasattr(node, "embeddings") and node.embeddings:
            for key, emb in node.embeddings.items():
                sample_dims.append((idx, key, len(emb)))
    if sample_dims:
        print(f"\nSample embedding dimensions: {sample_dims[:3]}")


def main():
    work_dir = Path("/tmp/compare_versions")
    work_dir.mkdir(exist_ok=True)

    # Download and analyze original
    print("Downloading ORIGINAL tree (Jan 10)...")
    original_path = work_dir / "original.pkl"
    download_version(ORIGINAL_VERSION, str(original_path))

    print("Loading original tree...")
    with open(original_path, "rb") as f:
        original_tree = pickle.load(f)

    analyze_tree(original_tree, "ORIGINAL TREE (Jan 10 - before incremental update)")

    # Download and analyze current
    print("\nDownloading CURRENT tree (Jan 19)...")
    current_path = work_dir / "current.pkl"
    download_version(CURRENT_VERSION, str(current_path))

    print("Loading current tree...")
    with open(current_path, "rb") as f:
        current_tree = pickle.load(f)

    analyze_tree(current_tree, "CURRENT TREE (Jan 19 - after incremental update)")

    # Compare
    print("\n" + "=" * 70)
    print("COMPARISON")
    print("=" * 70)

    orig_layers = set(original_tree.layer_to_nodes.keys())
    curr_layers = set(current_tree.layer_to_nodes.keys())

    print(f"Original layers: {sorted(orig_layers)}")
    print(f"Current layers: {sorted(curr_layers)}")

    missing_layers = orig_layers - curr_layers
    if missing_layers:
        print(f"\n*** MISSING LAYERS: {sorted(missing_layers)} ***")
        for layer in sorted(missing_layers):
            print(
                f"  Layer {layer} had {len(original_tree.layer_to_nodes[layer])} nodes"
            )

    orig_node_count = len(original_tree.all_nodes)
    curr_node_count = len(current_tree.all_nodes)
    print(
        f"\nNode count change: {orig_node_count} -> {curr_node_count} ({curr_node_count - orig_node_count:+d})"
    )


if __name__ == "__main__":
    main()
