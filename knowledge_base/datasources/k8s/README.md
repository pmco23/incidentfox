## Kubernetes datasource (local)

This folder is generated/used by the scripts in `scripts/` (run from `knowledge_base` root directory).

### Files
- **`raw/`**: extracted markdown docs (`.md` / `.mdx`) copied from the Kubernetes docs source.
- **`corpus.jsonl`**: one JSON record per doc:
  - `id`: stable sha1 of the source URL
  - `rel_path`: relative path inside the docs tree
  - `source_url`: provenance URL
  - `text`: document text (front matter stripped)
- **`raptor_tree.pkl`**: optional RAPTOR tree artifact produced by `scripts/ingest_k8s.py`

### Typical workflow
1. Fetch docs:
   - `python scripts/k8s_fetch_docs.py --out-dir datasources/k8s`
2. Build RAPTOR tree:
   - `python scripts/ingest_k8s.py --corpus datasources/k8s/corpus.jsonl --out-tree datasources/k8s/raptor_tree.pkl`
3. Visualize hierarchy:
   - `python scripts/visualize_tree_graph.py --tree datasources/k8s/raptor_tree.pkl --out datasources/k8s/tree.dot`
   - render with Graphviz: `dot -Tpng datasources/k8s/tree.dot -o datasources/k8s/tree.png`

### Fast pipeline validation (recommended before full ingest)
If you just want to verify the end-to-end pipeline works (ingest → pickle → visualize) without waiting hours:

- **Doc-sampling smoke test** (fast; caps docs, chunk count varies):
  - `python scripts/ingest_k8s.py --mode offline --smoke --progress`

- **Leaf-chunk sampling** (fastest + most predictable; great for “~100 nodes”):
  - `python scripts/ingest_k8s.py --mode offline --max-docs 50 --sample-chunks 100 --out-tree datasources/k8s/raptor_tree_sample100.pkl --progress`

Then visualize the sampled tree:
- `python scripts/visualize_tree_html.py --tree datasources/k8s/raptor_tree_sample100.pkl --out datasources/k8s/tree_sample100.html`

### Asking questions (CLI)
The HTML graph is for browsing. To test retrieval + QA, use:

- `PYTHONPATH=. python scripts/ask_tree.py --tree datasources/k8s/raptor_tree_gpt52_concepts.pkl --q "What is the Downward API?" --cache-embeddings --embedding-cache-path datasources/k8s/.cache/embeddings-gpt52.sqlite --print-context`

### Incremental updates (daily)
This repository's original RAPTOR build is a **batch** algorithm. We added a practical **approximate incremental update**
that updates **leaf nodes (layer 0)** and **their immediate parents (layer 1)** without rebuilding the full hierarchy.

- **Pros**: much faster than full rebuilds for small daily deltas; only re-summarizes touched clusters.
- **Cons**: it will drift from the globally optimal clustering; plan on periodic full rebuilds (weekly/monthly).

To update an existing tree with new text:
- `PYTHONPATH=. python scripts/incremental_update_tree.py --tree datasources/k8s/raptor_tree.pkl --text-file path/to/new_doc.md --out-tree datasources/k8s/raptor_tree_updated.pkl`


