#!/usr/bin/env python3
"""
ECS task script to restore the original 6-layer tree and merge OTel content.

This script:
1. Downloads the original tree (Jan 10 version with 6 layers)
2. Downloads OTel content
3. Builds a small OTel tree from the content
4. Merges the OTel tree into the original using the new safe merge logic
5. Verifies the result has 6 layers
6. Uploads the merged tree to S3
"""

import logging
import os
import pickle
import subprocess
import sys
from pathlib import Path

# Add the app directory to the path for imports
sys.path.insert(0, "/app")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

# Configuration
S3_BUCKET = "raptor-kb-trees-103002841599"
TREE_NAME = "mega_ultra_v2"
ORIGINAL_VERSION_ID = (
    "9Jwi23uNj369xQMlVbQA_T1ilnjew.QM"  # Jan 10 - original 6-layer tree
)
OTEL_CONTENT_KEY = "otel/content.txt"


def download_from_s3(s3_path: str, local_path: str) -> None:
    """Download file from S3."""
    logger.info(f"Downloading s3://{S3_BUCKET}/{s3_path} to {local_path}")
    subprocess.run(
        ["aws", "s3", "cp", f"s3://{S3_BUCKET}/{s3_path}", local_path], check=True
    )


def download_version_from_s3(s3_key: str, version_id: str, local_path: str) -> None:
    """Download a specific version of a file from S3."""
    logger.info(
        f"Downloading s3://{S3_BUCKET}/{s3_key} (version {version_id}) to {local_path}"
    )
    subprocess.run(
        [
            "aws",
            "s3api",
            "get-object",
            "--bucket",
            S3_BUCKET,
            "--key",
            s3_key,
            "--version-id",
            version_id,
            local_path,
        ],
        check=True,
    )


def upload_to_s3(local_path: str, s3_path: str) -> None:
    """Upload file to S3."""
    logger.info(f"Uploading {local_path} to s3://{S3_BUCKET}/{s3_path}")
    subprocess.run(
        ["aws", "s3", "cp", local_path, f"s3://{S3_BUCKET}/{s3_path}"], check=True
    )


def analyze_tree(tree, label: str) -> None:
    """Print tree structure analysis."""
    logger.info(f"\n{'=' * 60}")
    logger.info(f"{label}")
    logger.info(f"{'=' * 60}")
    logger.info(f"  num_layers: {tree.num_layers}")
    logger.info(f"  all_nodes: {len(tree.all_nodes)}")
    logger.info(f"  leaf_nodes: {len(tree.leaf_nodes)}")
    for layer, nodes in sorted(tree.layer_to_nodes.items()):
        logger.info(f"  Layer {layer}: {len(nodes)} nodes")


def detect_embedding_info(tree):
    """Detect embedding key and dimension from tree."""
    for node in list(tree.all_nodes.values())[:10]:
        if hasattr(node, "embeddings") and node.embeddings:
            for key, emb in node.embeddings.items():
                return key, len(emb)
    raise ValueError("Could not detect embedding info from tree")


def get_embedding_model_for_dim(dim: int):
    """Get the appropriate embedding model for the dimension."""
    from raptor.EmbeddingModels import OpenAIEmbeddingModel

    if dim == 3072:
        return OpenAIEmbeddingModel(model="text-embedding-3-large")
    elif dim == 1536:
        return OpenAIEmbeddingModel(model="text-embedding-ada-002")
    else:
        raise ValueError(f"Unknown embedding dimension: {dim}")


def main():
    work_dir = Path("/tmp/restore_merge")
    work_dir.mkdir(exist_ok=True)

    # Step 1: Download original tree (6-layer version)
    logger.info("Step 1: Downloading original 6-layer tree from S3...")
    original_tree_path = work_dir / "original_tree.pkl"
    download_version_from_s3(
        f"trees/{TREE_NAME}/{TREE_NAME}.pkl",
        ORIGINAL_VERSION_ID,
        str(original_tree_path),
    )

    logger.info("Loading original tree...")
    with open(original_tree_path, "rb") as f:
        original_tree = pickle.load(f)

    analyze_tree(original_tree, "ORIGINAL TREE (6-layer)")

    # Verify it has 6 layers
    if original_tree.num_layers != 5:  # num_layers is 0-indexed max layer
        logger.warning(
            f"Expected num_layers=5 (6 layers), got {original_tree.num_layers}"
        )

    # Detect embedding settings
    embedding_key, embedding_dim = detect_embedding_info(original_tree)
    logger.info(f"Detected embedding: key='{embedding_key}', dim={embedding_dim}")

    # Step 2: Download OTel content
    logger.info("\nStep 2: Downloading OTel content...")
    otel_content_path = work_dir / "otel_content.txt"
    download_from_s3(OTEL_CONTENT_KEY, str(otel_content_path))

    otel_content = otel_content_path.read_text(encoding="utf-8")
    logger.info(f"OTel content: {len(otel_content):,} characters")

    # Step 3: Use incremental update to add OTel content directly
    # This avoids building a separate tree which requires UMAP clustering
    logger.info("\nStep 3: Adding OTel content incrementally...")

    from raptor.RetrievalAugmentation import (
        RetrievalAugmentation,
        RetrievalAugmentationConfig,
    )

    embedding_model = get_embedding_model_for_dim(embedding_dim)

    # Configure to match original tree's settings
    config = RetrievalAugmentationConfig(
        tr_context_embedding_model=embedding_key,
        tr_embedding_model=embedding_model,
        tb_cluster_embedding_model=embedding_key,
        tb_embedding_models={embedding_key: embedding_model},
    )

    # Create RA wrapper around original tree
    main_ra = RetrievalAugmentation(config=config, tree=original_tree)

    # Add OTel content using the new safe incremental update
    main_ra.add_to_existing(
        otel_content,
        similarity_threshold=0.25,
        max_children_for_summary=50,
        max_summary_context_tokens=12000,
        use_safe_propagation=True,  # Use the new layer-by-layer propagation
    )

    merged_tree = main_ra.tree

    analyze_tree(merged_tree, "MERGED TREE (after incremental add)")

    # Step 4: Verify result
    logger.info("\nStep 4: Verifying merged tree...")

    expected_layers = 6  # layers 0-5
    actual_layers = merged_tree.num_layers + 1

    if actual_layers >= expected_layers:
        logger.info(
            f"✓ Tree has {actual_layers} layers (expected >= {expected_layers})"
        )
    else:
        logger.warning(
            f"✗ Tree has only {actual_layers} layers (expected >= {expected_layers})"
        )

    # Verify OTel content is present (original had 39023 leaves)
    otel_leaf_count = len(merged_tree.leaf_nodes) - 39023
    logger.info(f"  New leaf nodes (OTel): {otel_leaf_count}")
    logger.info(f"  Total leaf nodes: {len(merged_tree.leaf_nodes)}")
    logger.info(f"  Total all_nodes: {len(merged_tree.all_nodes)}")

    # Step 5: Save and upload
    logger.info("\nStep 5: Saving and uploading merged tree...")
    merged_tree_path = work_dir / "merged_tree.pkl"
    with open(merged_tree_path, "wb") as f:
        pickle.dump(merged_tree, f)

    upload_to_s3(str(merged_tree_path), f"trees/{TREE_NAME}/{TREE_NAME}.pkl")

    logger.info("\n" + "=" * 60)
    logger.info("INCREMENTAL UPDATE COMPLETE!")
    logger.info("=" * 60)
    logger.info(f"  Original tree: {54598} nodes, 6 layers")
    logger.info(
        f"  Merged tree: {len(merged_tree.all_nodes)} nodes, {merged_tree.num_layers + 1} layers"
    )
    logger.info(f"  New OTel leaves: {otel_leaf_count}")


if __name__ == "__main__":
    main()
