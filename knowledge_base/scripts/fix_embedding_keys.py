#!/usr/bin/env python3
"""
ECS task script to fix embedding key mismatch in the tree.

Some nodes have embeddings under 'OpenAI' key instead of 'EMB'.
This script re-keys all embeddings to use a consistent key.
"""

import logging
import os
import pickle
import subprocess
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

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


def main():
    work_dir = Path("/tmp/fix_keys")
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

    # Step 3: Detect existing keys and find the target key
    target_key = "EMB"  # The key used by the original mega_ultra_v2 tree

    keys_found = set()
    nodes_needing_fix = []
    nodes_already_correct = []
    nodes_missing_embeddings = []

    for idx, node in tree.all_nodes.items():
        if not hasattr(node, "embeddings") or not node.embeddings:
            nodes_missing_embeddings.append(idx)
            continue

        keys = list(node.embeddings.keys())
        keys_found.update(keys)

        if target_key in node.embeddings:
            nodes_already_correct.append(idx)
        else:
            nodes_needing_fix.append(idx)

    logger.info(f"  Embedding keys found in tree: {keys_found}")
    logger.info(f"  Nodes already using '{target_key}': {len(nodes_already_correct)}")
    logger.info(f"  Nodes needing fix: {len(nodes_needing_fix)}")
    logger.info(f"  Nodes with no embeddings: {len(nodes_missing_embeddings)}")

    if not nodes_needing_fix:
        logger.info("No nodes need fixing. Tree is already consistent.")
        return

    # Step 4: Re-key the embeddings
    logger.info(
        f"Step 3: Re-keying {len(nodes_needing_fix)} nodes to use '{target_key}'..."
    )

    for idx in nodes_needing_fix:
        node = tree.all_nodes[idx]
        # Get the first available embedding (should be under 'OpenAI' or similar)
        old_key = list(node.embeddings.keys())[0]
        embedding = node.embeddings[old_key]

        # Store under the target key
        node.embeddings[target_key] = embedding

        # Optionally remove the old key to save space (keeping both for now)
        # del node.embeddings[old_key]

    logger.info(f"  Re-keyed {len(nodes_needing_fix)} nodes")

    # Step 5: Verify
    logger.info("Step 4: Verifying fix...")
    verified_count = 0
    for idx, node in tree.all_nodes.items():
        if hasattr(node, "embeddings") and node.embeddings:
            if target_key in node.embeddings:
                verified_count += 1

    logger.info(f"  Nodes with '{target_key}' key: {verified_count}")

    # Step 6: Save fixed tree
    logger.info("Step 5: Saving fixed tree...")
    fixed_tree_local = work_dir / f"{TREE_NAME}_fixed.pkl"
    with open(fixed_tree_local, "wb") as f:
        pickle.dump(tree, f)

    # Step 7: Upload to S3
    logger.info("Step 6: Uploading fixed tree to S3...")
    upload_to_s3(str(fixed_tree_local), f"trees/{TREE_NAME}/{TREE_NAME}.pkl")

    logger.info("Done! Tree fixed.")
    logger.info(f"  Total nodes: {len(tree.all_nodes)}")
    logger.info(f"  Nodes re-keyed: {len(nodes_needing_fix)}")


if __name__ == "__main__":
    main()
