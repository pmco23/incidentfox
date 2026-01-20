#!/usr/bin/env python3
"""
ECS task script to incrementally add OTel docs to mega_ultra_v2 tree.

This script:
1. Downloads the OTel content from S3
2. Loads the mega_ultra_v2 tree
3. Runs incremental update
4. Saves the updated tree back to S3

Run this as an ECS task with the same image as the API server.
"""

import logging
import os
import pickle
import subprocess
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

# Imports from the RAPTOR library
from raptor import RetrievalAugmentation, RetrievalAugmentationConfig
from raptor.EmbeddingModels import OpenAIEmbeddingModel
from raptor.tree_structures import Tree

S3_BUCKET = "raptor-kb-trees-103002841599"
TREE_NAME = "mega_ultra_v2"


def download_from_s3(s3_path: str, local_path: str) -> None:
    """Download file from S3."""
    logger.info(f"Downloading s3://{S3_BUCKET}/{s3_path} to {local_path}")
    subprocess.run(
        ["aws", "s3", "cp", f"s3://{S3_BUCKET}/{s3_path}", local_path], check=True
    )


def upload_to_s3(local_path: str, s3_path: str) -> None:
    """Upload file to S3."""
    logger.info(f"Uploading {local_path} to s3://{S3_BUCKET}/{s3_path}")
    subprocess.run(
        ["aws", "s3", "cp", local_path, f"s3://{S3_BUCKET}/{s3_path}"], check=True
    )


def detect_embedding_info(tree: Tree) -> tuple[str, int]:
    """Detect embedding key and dimension from tree."""
    for node in tree.all_nodes.values():
        if hasattr(node, "embeddings") and node.embeddings:
            keys = list(node.embeddings.keys())
            if keys:
                key = keys[0]
                embedding = node.embeddings[key]
                dim = len(embedding) if embedding is not None else 1536
                return key, dim
    return "OpenAI", 1536


def get_embedding_model_for_dim(dim: int) -> OpenAIEmbeddingModel:
    """Get appropriate embedding model for dimension."""
    if dim == 3072:
        return OpenAIEmbeddingModel(model="text-embedding-3-large")
    else:
        return OpenAIEmbeddingModel(model="text-embedding-3-small")


def main():
    work_dir = Path("/tmp/otel_update")
    work_dir.mkdir(exist_ok=True)

    tree_local = work_dir / f"{TREE_NAME}.pkl"
    content_local = work_dir / "content.txt"

    # Step 1: Download tree and content
    logger.info("Step 1: Downloading files from S3...")
    download_from_s3(f"trees/{TREE_NAME}/{TREE_NAME}.pkl", str(tree_local))
    download_from_s3("otel/content.txt", str(content_local))

    # Step 2: Load tree
    logger.info("Step 2: Loading tree...")
    with open(tree_local, "rb") as f:
        tree = pickle.load(f)

    logger.info(
        f"  Tree loaded: {len(tree.all_nodes)} nodes, {len(tree.leaf_nodes)} leaves"
    )

    embedding_key, embedding_dim = detect_embedding_info(tree)
    logger.info(f"  Embedding key: {embedding_key}, dimension: {embedding_dim}")

    # Step 3: Create RetrievalAugmentation wrapper
    # IMPORTANT: Both retriever AND builder must use the same embedding key
    # to ensure new nodes have embeddings under the same key as existing nodes.
    embedding_model = get_embedding_model_for_dim(embedding_dim)
    config = RetrievalAugmentationConfig(
        tr_context_embedding_model=embedding_key,
        tr_embedding_model=embedding_model,
        tb_cluster_embedding_model=embedding_key,
        tb_embedding_models={embedding_key: embedding_model},
    )
    ra = RetrievalAugmentation(config=config, tree=tree)

    # Step 4: Load OTel content
    logger.info("Step 3: Loading OTel content...")
    content = content_local.read_text(encoding="utf-8")
    logger.info(f"  Content size: {len(content):,} characters")

    # Step 5: Run incremental update
    logger.info(
        "Step 4: Running incremental update (this will take several minutes)..."
    )
    initial_nodes = len(ra.tree.all_nodes)
    initial_leaves = len(ra.tree.leaf_nodes)

    ra.add_to_existing(
        content,
        similarity_threshold=0.25,
        auto_rebuild_upper_layers=True,
    )

    final_nodes = len(ra.tree.all_nodes)
    final_leaves = len(ra.tree.leaf_nodes)
    new_leaves = final_leaves - initial_leaves

    logger.info("  Incremental update complete!")
    logger.info(f"  New leaves added: {new_leaves}")
    logger.info(f"  Total nodes: {initial_nodes} -> {final_nodes}")

    # Step 6: Save updated tree
    logger.info("Step 5: Saving updated tree...")
    updated_tree_local = work_dir / f"{TREE_NAME}_with_otel.pkl"
    with open(updated_tree_local, "wb") as f:
        pickle.dump(ra.tree, f)

    # Step 7: Upload to S3
    logger.info("Step 6: Uploading to S3...")
    upload_to_s3(str(updated_tree_local), f"trees/{TREE_NAME}/{TREE_NAME}.pkl")

    logger.info("Done! Tree updated with OTel demo docs.")
    logger.info(f"  New leaves: {new_leaves}")
    logger.info(f"  Total nodes: {final_nodes}")


if __name__ == "__main__":
    main()
