#!/usr/bin/env python3
"""
Export a saved RAPTOR tree (pickle) into a Graphviz DOT graph for hierarchy visualization.

Output:
- .dot file you can render with Graphviz, e.g.:
  dot -Tpng tree.dot -o tree.png
  dot -Tsvg tree.dot -o tree.svg

This is intentionally dependency-light (stdlib only).
"""

from __future__ import annotations

import argparse
import pickle
import re
from pathlib import Path
from typing import Dict, Optional

from raptor.tree_structures import Tree


def _escape_dot_label(s: str) -> str:
    # Keep DOT happy; also avoid huge labels.
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _node_to_layer(tree: Tree) -> Dict[int, int]:
    idx_to_layer: Dict[int, int] = {}
    for layer, nodes in tree.layer_to_nodes.items():
        for n in nodes:
            idx_to_layer[n.index] = layer
    return idx_to_layer


def write_dot(
    tree: Tree,
    out_path: Path,
    max_label_chars: int = 140,
    min_layer: Optional[int] = None,
    max_layer: Optional[int] = None,
    max_nodes: Optional[int] = None,
) -> None:
    idx_to_layer = _node_to_layer(tree)

    def layer_ok(layer: int) -> bool:
        if min_layer is not None and layer < min_layer:
            return False
        if max_layer is not None and layer > max_layer:
            return False
        return True

    node_ids = sorted(tree.all_nodes.keys())
    if max_nodes is not None:
        node_ids = node_ids[:max_nodes]
    node_id_set = set(node_ids)

    lines = []
    lines.append("digraph raptor_tree {")
    lines.append('  graph [rankdir="TB"];')
    lines.append('  node [shape="box", fontsize=9];')
    lines.append('  edge [color="#999999"];')

    for idx in node_ids:
        node = tree.all_nodes[idx]
        layer = idx_to_layer.get(idx, -1)
        if not layer_ok(layer):
            continue
        text = node.text or ""
        text = _escape_dot_label(text[:max_label_chars])
        label = f"{idx} (L{layer})\\n{text}"
        lines.append(f'  n{idx} [label="{label}"];')

    for idx in node_ids:
        node = tree.all_nodes[idx]
        parent_layer = idx_to_layer.get(idx, -1)
        if not layer_ok(parent_layer):
            continue
        for child_idx in sorted(node.children):
            if child_idx not in node_id_set:
                continue
            child_layer = idx_to_layer.get(child_idx, -1)
            if not layer_ok(child_layer):
                continue
            lines.append(f"  n{idx} -> n{child_idx};")

    lines.append("}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--tree",
        required=True,
        help="Path to RAPTOR tree pickle (e.g. datasources/k8s/raptor_tree.pkl)",
    )
    ap.add_argument("--out", required=True, help="Output .dot path (e.g. tree.dot)")
    ap.add_argument(
        "--max-label-chars",
        type=int,
        default=140,
        help="Max chars from node text to include in label (default: 140)",
    )
    ap.add_argument(
        "--min-layer", type=int, default=None, help="Only include nodes >= this layer"
    )
    ap.add_argument(
        "--max-layer", type=int, default=None, help="Only include nodes <= this layer"
    )
    ap.add_argument(
        "--max-nodes", type=int, default=None, help="Cap number of nodes exported"
    )
    args = ap.parse_args(argv)

    tree_path = Path(args.tree)
    with open(tree_path, "rb") as f:
        obj = pickle.load(f)
    if not isinstance(obj, Tree):
        raise TypeError(f"Pickle did not contain a raptor.Tree: got {type(obj)}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    write_dot(
        obj,
        out_path=out_path,
        max_label_chars=args.max_label_chars,
        min_layer=args.min_layer,
        max_layer=args.max_layer,
        max_nodes=args.max_nodes,
    )
    print(f"[visualize_tree_graph] wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
