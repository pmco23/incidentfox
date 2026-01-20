#!/usr/bin/env python3
"""
Export a saved RAPTOR tree (pickle) into an interactive HTML graph.

This generates:
- an HTML file that visualizes the hierarchy with pan/zoom, hover tooltips, and a search box
- (optionally) a JSON file with nodes/edges to reuse elsewhere

Rendering approach:
- Uses vis-network in the browser for convenience (loaded via CDN).
  If you need fully offline viewing, download the vis-network assets and update the script/HTML accordingly.
"""

from __future__ import annotations

import argparse
import html
import json
import pickle
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from raptor.tree_structures import Tree


def _compact_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def _escape_html_text(s: str) -> str:
    # Escape corpus text so it doesn't get interpreted as HTML in tooltips.
    return html.escape(s or "", quote=True)


def _node_to_layer(tree: Tree) -> Dict[int, int]:
    idx_to_layer: Dict[int, int] = {}
    for layer, nodes in tree.layer_to_nodes.items():
        for n in nodes:
            idx_to_layer[n.index] = layer
    return idx_to_layer


def _palette() -> List[str]:
    # Distinct-ish colors for layers.
    return [
        "#4e79a7",
        "#f28e2b",
        "#e15759",
        "#76b7b2",
        "#59a14f",
        "#edc948",
        "#b07aa1",
        "#ff9da7",
        "#9c755f",
        "#bab0ab",
    ]


def build_graph_data(
    tree: Tree,
    max_label_chars: int = 120,
    min_layer: Optional[int] = None,
    max_layer: Optional[int] = None,
    max_nodes: Optional[int] = None,
) -> Tuple[List[dict], List[dict]]:
    idx_to_layer = _node_to_layer(tree)
    colors = _palette()
    max_layer_present = max(idx_to_layer.values()) if idx_to_layer else 0

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

    # If the graph is large, start collapsed to keep the initial view usable.
    # We show only top-layer nodes (highest layer number) + a synthetic ROOT node.
    collapse_by_default = (max_nodes is None) and (len(node_id_set) > 1500)
    top_layer_visible_cap = 80 if collapse_by_default else None

    # Choose which top-layer nodes are initially visible to avoid rendering a single ultra-wide row.
    top_layer_nodes = [
        idx
        for idx in node_ids
        if idx_to_layer.get(idx, -1) == max_layer_present
        and layer_ok(max_layer_present)
    ]
    if top_layer_visible_cap is not None:
        top_layer_nodes_sorted = sorted(
            top_layer_nodes,
            key=lambda i: (
                len(tree.all_nodes[i].children)
                if isinstance(tree.all_nodes[i].children, set)
                else 0
            ),
            reverse=True,
        )
        top_layer_visible = set(top_layer_nodes_sorted[:top_layer_visible_cap])
    else:
        top_layer_visible = set(top_layer_nodes)

    nodes: List[dict] = []
    # Synthetic root to anchor the top layer and avoid a "floating" initial view.
    root_id = "__root__"
    nodes.append(
        {
            "id": root_id,
            "label": "ROOT",
            "title": "<b>ROOT</b><br/>Synthetic node to anchor the top layer.",
            "group": "root",
            "color": {"background": "#111111", "border": "#111111"},
            "font": {"size": 14, "color": "#ffffff"},
            "shape": "box",
            "fixed": {"x": False, "y": False},
        }
    )

    for idx in node_ids:
        n = tree.all_nodes[idx]
        layer = idx_to_layer.get(idx, -1)
        if not layer_ok(layer):
            continue
        # NOTE: `n.text` is plain text, but may contain Markdown/HTML-looking characters from docs.
        # We keep the raw text for a click-to-open details panel (rendered via `textContent` in JS),
        # and keep hover tooltips SHORT + plain to avoid giant overlays.
        raw_text = (n.text or "").strip()
        compact = _compact_ws(raw_text)
        snippet = (
            compact[: max(0, int(max_label_chars))]
            if max_label_chars is not None
            else compact
        )
        if max_label_chars is not None and len(compact) > int(max_label_chars):
            snippet = snippet.rstrip() + "…"
        color = colors[layer % len(colors)] if layer >= 0 else "#cccccc"
        children_count = len(n.children) if isinstance(n.children, set) else 0
        hidden = False
        if collapse_by_default:
            if layer < max_layer_present:
                hidden = True
            elif layer == max_layer_present and idx not in top_layer_visible:
                hidden = True
        nodes.append(
            {
                # IMPORTANT: normalize all IDs to strings to avoid vis-network mixed-id bugs
                # (ROOT is a string id; numeric ids can come back from events as strings).
                "id": str(idx),
                "label": f"{idx} (L{layer}) [{children_count}]",
                # vis-network tooltips are not reliably HTML-rendered across environments;
                # keep `title` as short plain text.
                "title": f"Node {idx} (Layer {layer}) — {snippet}",
                # Full raw node text for the details panel (rendered as plain text client-side).
                "_text": raw_text,
                # Optional keyword list for browsing / search / graph relationships.
                "_keywords": list(getattr(n, "keywords", []) or []),
                "group": f"layer_{layer}",
                "color": {"background": color, "border": "#333333"},
                "font": {"size": 12},
                "shape": "box",
                "hidden": hidden,
                # Keep some metadata for client-side expansion/collapse logic.
                "_layer": layer,
            }
        )

    edges: List[dict] = []
    # Anchor top-layer nodes under ROOT so the collapsed view still shows structure.
    for idx in node_ids:
        layer = idx_to_layer.get(idx, -1)
        if not layer_ok(layer):
            continue
        if layer == max_layer_present:
            hidden = collapse_by_default and (idx not in top_layer_visible)
            edges.append(
                {
                    "from": root_id,
                    "to": str(idx),
                    "arrows": "to",
                    "color": {"color": "#cccccc"},
                    "hidden": hidden,
                }
            )

    for idx in node_ids:
        parent_layer = idx_to_layer.get(idx, -1)
        if not layer_ok(parent_layer):
            continue
        parent = tree.all_nodes[idx]
        for child_idx in parent.children:
            if child_idx not in node_id_set:
                continue
            child_layer = idx_to_layer.get(child_idx, -1)
            if not layer_ok(child_layer):
                continue
            # Hide edges if either endpoint is hidden (in collapsed mode).
            hidden = False
            if collapse_by_default:
                hidden = (child_layer < max_layer_present) or (
                    parent_layer < max_layer_present
                )
            edges.append(
                {
                    "from": str(idx),
                    "to": str(child_idx),
                    "arrows": "to",
                    "hidden": hidden,
                }
            )

    return nodes, edges


def write_html(
    out_path: Path, nodes: List[dict], edges: List[dict], title: str
) -> None:
    # Load vis-network via CDN. Keep HTML simple and readable.
    # Note: no bare URLs in user-facing text; this is code.
    html = f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    <style>
      body {{ font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; margin: 0; }}
      #topbar {{ display: flex; gap: 12px; align-items: center; padding: 10px 12px; border-bottom: 1px solid #eee; }}
      #search {{ width: 420px; max-width: 60vw; padding: 8px 10px; }}
      #main {{ display: flex; width: 100vw; height: calc(100vh - 52px); }}
      #network {{ flex: 1 1 auto; min-width: 0; }}
      #details {{ width: 420px; max-width: 40vw; border-left: 1px solid #eee; padding: 10px 12px; overflow: auto; display: none; }}
      #details h3 {{ margin: 0 0 8px 0; font-size: 14px; }}
      #details .meta {{ color: #666; font-size: 12px; margin-bottom: 8px; }}
      #details pre {{ white-space: pre-wrap; word-break: break-word; background: #fafafa; border: 1px solid #eee; padding: 10px; border-radius: 6px; }}
      #details .close {{ float: right; }}
      .hint {{ color: #666; font-size: 12px; }}
      button {{ padding: 8px 10px; }}
    </style>
    <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
  </head>
  <body>
    <div id="topbar">
      <input id="search" placeholder="Search node label / content (substring)..." />
      <button id="fit">Fit</button>
      <button id="reset">Reset selection</button>
      <span class="hint">Tip: click nodes to focus; scroll to zoom; drag to pan.</span>
      <span class="hint">Nodes: {len(nodes)} | Edges: {len(edges)}</span>
    </div>
    <div id="main">
      <div id="network"></div>
      <div id="details">
        <button class="close" id="detailsClose">Close</button>
        <h3 id="detailsTitle">Node</h3>
        <div class="meta" id="detailsMeta"></div>
        <pre id="detailsText"></pre>
      </div>
    </div>

    <script>
      // Lazy-load graph: render a small top slice first, then add children on click.
      // This avoids vis-network hierarchical layout doing expensive work for thousands of nodes upfront.
      const ALL_NODES_LIST = {json.dumps(nodes, ensure_ascii=False)};
      const ALL_EDGES_LIST = {json.dumps(edges, ensure_ascii=False)};

      const ROOT_ID = "__root__";
      const ROOT_NODE = {{
        id: ROOT_ID,
        label: "ROOT",
        title: "ROOT — Synthetic node to anchor the top layer.",
        group: "root",
        color: {{ background: "#111111", border: "#111111" }},
        font: {{ size: 14, color: "#ffffff" }},
        shape: "box"
      }};

      const nodeById = new Map();
      for (const n of ALL_NODES_LIST) nodeById.set(n.id, n);

      // parent -> [childId]
      const childrenByParent = new Map();
      for (const e of ALL_EDGES_LIST) {{
        if (!childrenByParent.has(e.from)) childrenByParent.set(e.from, []);
        childrenByParent.get(e.from).push(e.to);
      }}

      // Determine top layer
      let maxLayer = 0;
      for (const n of ALL_NODES_LIST) {{
        if (typeof n._layer === "number" && n._layer > maxLayer) maxLayer = n._layer;
      }}

      // Pick a limited number of top-layer nodes to show initially, prioritizing nodes with more children.
      const topNodes = ALL_NODES_LIST.filter(n => n._layer === maxLayer);
      topNodes.sort((a, b) => {{
        const ca = (childrenByParent.get(a.id) || []).length;
        const cb = (childrenByParent.get(b.id) || []).length;
        return cb - ca;
      }});
      const INITIAL_TOP_CAP = 40;
      const initialTop = topNodes.slice(0, Math.min(INITIAL_TOP_CAP, topNodes.length));

      const initialNodes = [ROOT_NODE, ...initialTop];
      const initialEdges = initialTop.map(n => ({{
        from: ROOT_ID,
        to: n.id,
        arrows: "to",
        color: {{ color: "#cccccc" }}
      }}));

      const nodes = new vis.DataSet(initialNodes);
      const edges = new vis.DataSet(initialEdges);

      const container = document.getElementById("network");
      const data = {{ nodes, edges }};
      const options = {{
        layout: {{
          hierarchical: {{
            enabled: true,
            direction: "LR",
            sortMethod: "directed",
            levelSeparation: 220,
            nodeSpacing: 40
          }}
        }},
        interaction: {{
          hover: true,
          navigationButtons: true,
          keyboard: true
        }},
        physics: {{
          enabled: false
        }}
      }};

      const network = new vis.Network(container, data, options);

      function visibleNodeIds() {{
        return nodes.get().map(n => n.id);
      }}

      function fit() {{
        const ids = visibleNodeIds();
        if (!ids.length) return;
        network.fit({{
          nodes: ids,
          animation: {{ duration: 400, easingFunction: "easeInOutQuad" }}
        }});
      }}

      document.getElementById("fit").addEventListener("click", fit);
      document.getElementById("reset").addEventListener("click", () => {{
        nodes.clear();
        edges.clear();
        nodes.add(initialNodes);
        edges.add(initialEdges);
        network.unselectAll();
        fit();
      }});

      function ensureNode(id) {{
        const existing = nodes.get(id);
        if (existing != null) {{
          // If a node was added in a "hidden" state (common in large graphs), unhide it on demand.
          if (existing.hidden) nodes.update({{ id, hidden: false }});
          return;
        }}
        const n = nodeById.get(id);
        if (n) {{
          // IMPORTANT: expanded nodes must be visible; the exporter may mark most nodes hidden
          // when collapse-by-default is enabled for large trees.
          const nn = Object.assign({{}}, n, {{ hidden: false }});
          nodes.add(nn);
        }}
      }}
      function ensureEdge(from, to) {{
        const existing = edges.get({{
          filter: (e) => e.from === from && e.to === to
        }});
        if (existing && existing.length) {{
          // Unhide if this edge exists but was hidden by the exporter.
          const e0 = existing[0];
          if (e0 && e0.hidden) edges.update({{ id: e0.id, hidden: false }});
          return;
        }}
        edges.add({{ from, to, arrows: "to", hidden: false }});
      }}

      const MAX_EXPAND = 120;
      function expandNodeChildren(nodeId) {{
        if (nodeId === ROOT_ID) return;
        const children = (childrenByParent.get(nodeId) || []);
        if (children.length > MAX_EXPAND) {{
          const ok = window.confirm(
            "This node has " + children.length + " children. Expanding all may be slow.\\n\\n" +
            "Expand first " + MAX_EXPAND + "?"
          );
          if (!ok) return;
        }}
        const slice = children.slice(0, MAX_EXPAND);
        for (const childId of slice) {{
          ensureNode(childId);
          ensureEdge(nodeId, childId);
        }}
      }}

      network.on("selectNode", (params) => {{
        if (!params.nodes || !params.nodes.length) return;
        const id = params.nodes[0];
        expandNodeChildren(id);

        // Show details panel (full node text) without interpreting it as HTML.
        const details = document.getElementById("details");
        const t = document.getElementById("detailsTitle");
        const m = document.getElementById("detailsMeta");
        const pre = document.getElementById("detailsText");
        if (id === ROOT_ID) {{
          t.textContent = "ROOT";
          m.textContent = "Synthetic node";
          pre.textContent = "This node is only used to anchor the top layer visually.";
          details.style.display = "block";
          return;
        }}
        const n = nodeById.get(id);
        if (n) {{
          t.textContent = (n.label || ("Node " + id));
          const layer = (typeof n._layer === "number") ? n._layer : "?";
          const childCount = (childrenByParent.get(id) || []).length;
          const kws = Array.isArray(n._keywords) ? n._keywords : [];
          const kwStr = kws.length ? (" • keywords: " + kws.slice(0, 12).join(", ")) : "";
          m.textContent = "Layer " + layer + " • children: " + childCount + kwStr;
          pre.textContent = (n._text || "").toString();
          details.style.display = "block";
        }}
      }});

      document.getElementById("detailsClose").addEventListener("click", () => {{
        document.getElementById("details").style.display = "none";
      }});

      const search = document.getElementById("search");
      search.addEventListener("input", () => {{
        const q = search.value.trim().toLowerCase();
        if (!q) {{
          network.unselectAll();
          return;
        }}
        const matches = ALL_NODES_LIST
          .filter(n =>
            (n.label || "").toLowerCase().includes(q) ||
            (n.title || "").toLowerCase().includes(q) ||
            (n._text || "").toLowerCase().includes(q) ||
            ((Array.isArray(n._keywords) ? n._keywords.join(\" \") : \"\").toLowerCase().includes(q))
          )
          .slice(0, 25); // don't select too many at once
        const ids = matches.map(m => m.id);
        for (const id of ids) ensureNode(id);
        network.selectNodes(ids);
        if (ids.length) {{
          network.focus(ids[0], {{ scale: 1.1, animation: true }});
        }}
      }});

      // Fit initial view after first draw
      network.once("afterDrawing", () => {{
        fit();
        setTimeout(fit, 300);
      }});
    </script>
  </body>
</html>
"""
    out_path.write_text(html, encoding="utf-8")


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", required=True, help="Path to RAPTOR tree pickle")
    ap.add_argument("--out", required=True, help="Output .html path")
    ap.add_argument(
        "--out-json",
        default=None,
        help="Optional output .json path containing {nodes, edges}",
    )
    ap.add_argument(
        "--max-label-chars",
        type=int,
        default=120,
        help="Max chars from node text to include in tooltip label (default: 120)",
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
    ap.add_argument("--title", default="RAPTOR Tree", help="HTML page title")
    args = ap.parse_args(argv)

    tree_path = Path(args.tree)
    with open(tree_path, "rb") as f:
        obj = pickle.load(f)
    if not isinstance(obj, Tree):
        raise TypeError(f"Pickle did not contain a raptor.Tree: got {type(obj)}")

    nodes, edges = build_graph_data(
        obj,
        max_label_chars=args.max_label_chars,
        min_layer=args.min_layer,
        max_layer=args.max_layer,
        max_nodes=args.max_nodes,
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_html(out_path, nodes, edges, title=args.title)

    if args.out_json:
        out_json = Path(args.out_json)
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(
            json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False),
            encoding="utf-8",
        )

    print(f"[visualize_tree_html] wrote: {out_path}")
    if args.out_json:
        print(f"[visualize_tree_html] wrote: {args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
