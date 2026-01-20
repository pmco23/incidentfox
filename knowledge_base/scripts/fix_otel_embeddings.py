#!/usr/bin/env python3
"""
ECS task script to fix OTel node embeddings that have wrong dimension.

The OTel nodes were added with 1536-dim embeddings but the tree uses
3072-dim embeddings. This script re-embeds those nodes with the correct model.
"""

import logging
import os
import pickle
import subprocess
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

# Imports from the RAPTOR library
from raptor.EmbeddingModels import OpenAIEmbeddingModel

S3_BUCKET = "raptor-kb-trees-103002841599"
TREE_NAME = "mega_ultra_v2"
TARGET_DIM = 3072
EMBEDDING_KEY = "EMB"


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


def main():
    work_dir = Path("/tmp/fix_otel")
    work_dir.mkdir(exist_ok=True)

    tree_local = work_dir / f"{TREE_NAME}.pkl"

    # Step 1: Download tree
    logger.info("Step 1: Downloading tree from S3...")
    download_from_s3(f"trees/{TREE_NAME}/{TREE_NAME}.pkl", str(tree_local))

    # Step 2: Load tree
    logger.info("Step 2: Loading tree...")
    with open(tree_local, "rb") as f:
        tree = pickle.load(f)

    logger.info(
        f"  Tree loaded: {len(tree.all_nodes)} nodes, {len(tree.leaf_nodes)} leaves"
    )

    # Step 3: Find nodes with wrong dimension
    logger.info("Step 3: Finding nodes with wrong embedding dimension...")
    wrong_dim_nodes = []
    correct_dim_nodes = []
    missing_embedding_nodes = []

    for idx, node in tree.all_nodes.items():
        if not hasattr(node, "embeddings") or not node.embeddings:
            missing_embedding_nodes.append(idx)
            continue

        emb = node.embeddings.get(EMBEDDING_KEY)
        if emb is None:
            missing_embedding_nodes.append(idx)
        elif len(emb) != TARGET_DIM:
            wrong_dim_nodes.append(idx)
        else:
            correct_dim_nodes.append(idx)

    logger.info(f"  Nodes with correct {TARGET_DIM}-dim: {len(correct_dim_nodes)}")
    logger.info(f"  Nodes with wrong dimension: {len(wrong_dim_nodes)}")
    logger.info(f"  Nodes missing embeddings: {len(missing_embedding_nodes)}")

    if not wrong_dim_nodes:
        logger.info("No nodes need fixing. Tree is already consistent.")
        return

    # Log some sample wrong dimensions
    sample_nodes = wrong_dim_nodes[:5]
    for idx in sample_nodes:
        node = tree.all_nodes[idx]
        dim = len(node.embeddings[EMBEDDING_KEY])
        logger.info(f"  Node {idx}: dim={dim}")

    # Step 4: Re-embed nodes with wrong dimension
    logger.info(
        f"Step 4: Re-embedding {len(wrong_dim_nodes)} nodes with text-embedding-3-large..."
    )
    embedding_model = OpenAIEmbeddingModel(model="text-embedding-3-large")

    fixed_count = 0
    for i, idx in enumerate(wrong_dim_nodes):
        node = tree.all_nodes[idx]
        text = getattr(node, "text", "")

        if not text:
            logger.warning(f"  Node {idx} has no text, skipping")
            continue

        try:
            new_embedding = embedding_model.create_embedding(text)
            node.embeddings[EMBEDDING_KEY] = new_embedding
            fixed_count += 1

            if fixed_count % 50 == 0:
                logger.info(f"  Fixed {fixed_count}/{len(wrong_dim_nodes)} nodes...")
        except Exception as e:
            logger.error(f"  Failed to re-embed node {idx}: {e}")

    logger.info(f"  Re-embedded {fixed_count} nodes")

    # Step 5: Verify
    logger.info("Step 5: Verifying fix...")
    verified_count = 0
    wrong_count = 0
    for idx, node in tree.all_nodes.items():
        if hasattr(node, "embeddings") and node.embeddings:
            emb = node.embeddings.get(EMBEDDING_KEY)
            if emb is not None:
                if len(emb) == TARGET_DIM:
                    verified_count += 1
                else:
                    wrong_count += 1

    logger.info(f"  Nodes with {TARGET_DIM}-dim '{EMBEDDING_KEY}': {verified_count}")
    logger.info(f"  Nodes still with wrong dim: {wrong_count}")

    # Step 6: Save fixed tree
    logger.info("Step 6: Saving fixed tree...")
    fixed_tree_local = work_dir / f"{TREE_NAME}_fixed.pkl"
    with open(fixed_tree_local, "wb") as f:
        pickle.dump(tree, f)

    # Step 7: Upload to S3
    logger.info("Step 7: Uploading fixed tree to S3...")
    upload_to_s3(str(fixed_tree_local), f"trees/{TREE_NAME}/{TREE_NAME}.pkl")

    logger.info("Done! Tree embeddings fixed.")
    logger.info(f"  Nodes re-embedded: {fixed_count}")
    logger.info(f"  Total nodes with correct dim: {verified_count}")


if __name__ == "__main__":
    main()
