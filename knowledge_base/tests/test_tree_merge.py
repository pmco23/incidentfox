#!/usr/bin/env python3
"""
Tests for tree merging functionality.

Run with:
    pytest tests/test_tree_merge.py -v
    python tests/test_tree_merge.py  # standalone
"""

import sys
from pathlib import Path

# Ensure raptor module is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pytest
from raptor.tree_merge import merge_trees, merge_trees_incremental
from raptor.tree_structures import Node, Tree


def _make_dummy_node(
    index: int, text: str, children: set = None, layer: int = 0
) -> Node:
    """Create a dummy node with fake embeddings."""
    embeddings = {"EMB": np.random.rand(384).astype(np.float32).tolist()}
    return Node(
        text=text,
        index=index,
        children=children or set(),
        embeddings=embeddings,
        keywords=["test", f"node{index}"],
        metadata={"source": f"test_source_{index}", "layer": layer},
        original_content_ref=f"ref_{index}",
    )


def _make_simple_tree(prefix: str, num_leaves: int = 5) -> Tree:
    """Create a simple 2-layer tree for testing."""
    leaves = {}
    for i in range(num_leaves):
        node = _make_dummy_node(i, f"{prefix} leaf {i}", layer=0)
        leaves[i] = node

    # Create parent nodes (layer 1)
    parent1 = _make_dummy_node(
        num_leaves, f"{prefix} parent 0", children={0, 1, 2}, layer=1
    )
    parent2 = _make_dummy_node(
        num_leaves + 1, f"{prefix} parent 1", children={3, 4}, layer=1
    )

    all_nodes = {**leaves, parent1.index: parent1, parent2.index: parent2}
    root_nodes = {parent1.index: parent1, parent2.index: parent2}
    layer_to_nodes = {
        0: list(leaves.values()),
        1: [parent1, parent2],
    }

    return Tree(
        all_nodes=all_nodes,
        root_nodes=root_nodes,
        leaf_nodes=leaves,
        num_layers=1,
        layer_to_nodes=layer_to_nodes,
    )


class TestMergeTrees:
    """Tests for merge_trees function."""

    def test_merge_single_tree_returns_copy(self):
        """Merging a single tree should return a deep copy."""
        tree = _make_simple_tree("A")
        merged = merge_trees([tree], rebuild_upper_layers=False)

        # Should be a different object
        assert merged is not tree

        # But same structure
        assert len(merged.all_nodes) == len(tree.all_nodes)
        assert len(merged.leaf_nodes) == len(tree.leaf_nodes)

    def test_merge_two_trees_no_rebuild(self):
        """Merge two trees without rebuilding upper layers."""
        tree_a = _make_simple_tree("A", num_leaves=3)
        tree_b = _make_simple_tree("B", num_leaves=4)

        merged = merge_trees([tree_a, tree_b], rebuild_upper_layers=False)

        # Should have all leaves from both trees
        expected_leaves = len(tree_a.leaf_nodes) + len(tree_b.leaf_nodes)
        assert (
            len(merged.leaf_nodes) == expected_leaves
        ), f"Expected {expected_leaves} leaves, got {len(merged.leaf_nodes)}"

        # All nodes should have unique indices
        indices = list(merged.all_nodes.keys())
        assert len(indices) == len(set(indices)), "Duplicate indices found"

        # Verify no index collision
        max_idx = max(indices)
        assert max_idx >= expected_leaves - 1

    def test_merge_preserves_metadata(self):
        """Merged nodes should preserve their metadata."""
        tree_a = _make_simple_tree("A", num_leaves=2)
        tree_b = _make_simple_tree("B", num_leaves=2)

        merged = merge_trees([tree_a, tree_b], rebuild_upper_layers=False)

        # Check that metadata is preserved
        for node in merged.leaf_nodes.values():
            assert node.metadata is not None
            assert "source" in node.metadata
            assert node.original_content_ref is not None
            assert node.keywords is not None

    def test_merge_preserves_embeddings(self):
        """Merged nodes should have their embeddings preserved."""
        tree_a = _make_simple_tree("A", num_leaves=2)
        tree_b = _make_simple_tree("B", num_leaves=2)

        merged = merge_trees([tree_a, tree_b], rebuild_upper_layers=False)

        for node in merged.leaf_nodes.values():
            assert "EMB" in node.embeddings
            assert len(node.embeddings["EMB"]) == 384

    def test_merge_three_trees(self):
        """Merge three trees."""
        trees = [
            _make_simple_tree("A", num_leaves=3),
            _make_simple_tree("B", num_leaves=4),
            _make_simple_tree("C", num_leaves=5),
        ]

        merged = merge_trees(trees, rebuild_upper_layers=False)

        expected_leaves = 3 + 4 + 5
        assert len(merged.leaf_nodes) == expected_leaves

    def test_merge_empty_list_raises(self):
        """Merging an empty list should raise an error."""
        with pytest.raises(ValueError, match="At least one tree"):
            merge_trees([])

    def test_children_remapped_correctly(self):
        """Parent nodes should have their children indices remapped."""
        tree_a = _make_simple_tree("A", num_leaves=3)
        tree_b = _make_simple_tree("B", num_leaves=3)

        merged = merge_trees([tree_a, tree_b], rebuild_upper_layers=False)

        # Check that all children references are valid
        for node in merged.all_nodes.values():
            for child_idx in node.children:
                assert (
                    child_idx in merged.all_nodes
                ), f"Child index {child_idx} not found in merged tree"

    def test_layer_to_nodes_consistent(self):
        """layer_to_nodes should be consistent with all_nodes."""
        tree_a = _make_simple_tree("A", num_leaves=3)
        tree_b = _make_simple_tree("B", num_leaves=3)

        merged = merge_trees([tree_a, tree_b], rebuild_upper_layers=False)

        # All nodes in layer_to_nodes should be in all_nodes
        for layer, nodes in merged.layer_to_nodes.items():
            for node in nodes:
                assert (
                    node.index in merged.all_nodes
                ), f"Node {node.index} from layer {layer} not in all_nodes"


class TestMergeTreesIncremental:
    """Tests for merge_trees_incremental function."""

    def test_incremental_requires_builder(self):
        """Incremental merge should require a builder."""
        tree_a = _make_simple_tree("A")
        tree_b = _make_simple_tree("B")

        with pytest.raises(ValueError, match="builder is required"):
            merge_trees_incremental(tree_a, tree_b)


def run_standalone_tests():
    """Run tests without pytest."""
    print("=" * 60)
    print("Tree Merge Tests (Standalone)")
    print("=" * 60)

    tests = TestMergeTrees()
    test_methods = [m for m in dir(tests) if m.startswith("test_")]

    passed = 0
    failed = 0

    for method_name in test_methods:
        try:
            method = getattr(tests, method_name)
            method()
            print(f"✅ {method_name}")
            passed += 1
        except Exception as e:
            print(f"❌ {method_name}: {e}")
            failed += 1

    print()
    print(f"Results: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    success = run_standalone_tests()
    sys.exit(0 if success else 1)
