# RAPTOR parameter recommendations (practical guide)

This guide explains the most important knobs you’ll use in this repo’s RAPTOR pipeline (especially `scripts/ingest_k8s.py`), what each one changes, reasonable ranges, and how they interact.

## Mental model (what RAPTOR is optimizing)
- **Leaf nodes (L0)**: raw-ish chunks (the ground truth content).
- **Parent nodes (L1, L2, …)**: *summaries* of clusters of children.
- **Retrieval**: at query time, you retrieve a small set of nodes (often across layers) by embedding similarity, then pass their text into QA.

This creates two competing objectives:
- **Human browsing** wants **short, clean summaries** at higher layers.
- **Automated retrieval/QA** often benefits from **slightly richer summaries** (more keywords/coverage) to improve matching.

There is no single “best” setting for both; you choose a point on the spectrum.

## Chunking (most important for “chunks make sense”)

### `--tb-max-tokens`
Controls **leaf chunk size** (approx tokens). Larger = fewer leaf chunks; smaller = more chunks.

- **Typical range**: 300–1000
- **Good default for docs**: 600–900
- **Symptoms**
  - Too low: chunks feel fragmented; graph looks noisy; more embedding calls.
  - Too high: chunks feel multi-topic; retrieval may pull irrelevant content; summaries are harder.

### `--chunking`
Selects how text is split into leaf chunks.

- **`simple`**: fast sentence/newline splitter; can create incoherent chunks in docs with lots of lists/templates.
- **`markdown`**: structure-aware (headings + code fences). Usually best ROI for technical docs.
- **`semantic`**: embedding-based topic shift splitting. Best coherence, but costs more embeddings.

### Semantic chunking knobs (only when `--chunking semantic`)
- **`--semantic-unit sentence|paragraph`**
  - sentence: more granular, more embedding calls, more precise boundaries
  - paragraph: fewer calls, chunk boundaries often align with doc sections
- **`--semantic-sim-threshold`** (topic shift cutoff)
  - Higher = splits more aggressively
  - **Typical range**: 0.72–0.85
- **`--semantic-adaptive`**
  - Recommended: adapts threshold per document based on similarity distribution
- **`--semantic-min-chunk-tokens`**
  - Prevents “over-splitting” into tiny chunks
  - **Typical range**: 80–200

## Tree shape (how many levels, how wide the top is)

### `--auto-depth` + `--target-top-nodes`
This is your practical “how many levels?” control.

- With `--auto-depth`, RAPTOR keeps building layers until the current top layer has **<= target_top_nodes**.
- Lower `--target-top-nodes` ⇒ **more layers** (more abstraction).
- Higher `--target-top-nodes` ⇒ **fewer layers** (more flat).

**Typical range**:
- Human browsing: 10–30
- Balanced: 30–60
- Pure retrieval scaling: 50–100+

### `--tb-num-layers`
Hard cap on how many layers can be built.

- With `--auto-depth`, this is effectively a **safety cap** (max depth).
- Without `--auto-depth`, this is the **exact depth target** (unless RAPTOR early-stops).

**Typical range**: 3–8

### `--tb-summarization-length`
Controls how *long* each parent node summary can be (in tokens).

- **Human browsing**: 120–180
- **Balanced**: 180–240
- **Retrieval-heavy**: 250–400

**Symptoms**
- Too high: L1/L2 nodes look like “still raw text” (extractive, long, listy).
- Too low: parents become vague; retrieval may need to expand more children to find details.

**Important interaction**
- If you want a higher layer (L2+) to read “conceptual”, you usually need:
  - smaller summaries *and/or*
  - a smaller `--target-top-nodes` (so you actually build L2)

## Clustering (runtime + tree quality)

### `--reduction-dimension`
UMAP output dimension before clustering. Smaller is faster; too small can lose structure.

- **Typical range**: 4–10
- **Good default**: 6

### `--cluster-max-clusters`
Cap for GMM model selection during clustering. Lower is faster, but can underfit.

- **Typical range**: 6–25
- **Good default**: 8–12 for large corpora

### `--cluster-threshold`
How confidently a point must belong to a cluster (GMM membership threshold). Lower tends to produce more overlap / more assignments.

- **Typical range**: 0.05–0.25
- **Good default**: 0.1

### `--cluster-max-length-tokens`
RAPTOR tries to avoid clusters whose combined child text is too large to summarize by reclustering them.

- Larger value: fewer recluster passes (faster) but larger summary context.
- Smaller value: more reclustering (slower) but tighter clusters.

**Typical range**: 6000–14000

## Retrieval + QA (query behavior)

### `--tr-top-k`
How many nodes to retrieve into context for QA.

- **Typical range**: 8–20
- If your parents are short: you can increase top-k a bit.
- If parents are long: decrease top-k to avoid context bloat.

## Cost/perf knobs (OpenAI mode)

### `--cache-embeddings` + `--embedding-cache-path`
Strongly recommended. Caching makes iterative tuning practical.

### `--embed-max-workers`
Embedding concurrency.

- Too high: more rate limiting / retries
- Too low: slower
- **Good default**: 2–4 in OpenAI mode

## Recommended “starting recipes”

### Human-browsing first (clean summaries + extra abstraction)
- `--chunking markdown`
- `--tb-max-tokens 700–900`
- `--tb-summarization-length 140–200`
- `--auto-depth --target-top-nodes 10–25`
- `--tb-num-layers 6`

### Balanced (good browsing + decent retrieval)
- `--chunking markdown` (or `semantic` if you can afford the extra embedding calls)
- `--tb-max-tokens 700–900`
- `--tb-summarization-length 180–240`
- `--auto-depth --target-top-nodes 30–60`
- `--tb-num-layers 6`

### Retrieval-heavy scaling (less abstraction, richer parents)
- `--chunking semantic` (if you can cache embeddings)
- `--tb-max-tokens 900–1200`
- `--tb-summarization-length 280–400`
- `--auto-depth --target-top-nodes 50–100`
- `--tb-num-layers 6`

## Auto-tuning (what is feasible)
It’s feasible to automatically recommend good defaults by inspecting:
- leaf chunk count (estimated from tokens / max_tokens)
- chosen chunking mode (simple vs markdown vs semantic)
- your stated goal (human browsing vs retrieval)

But there’s no universal “optimal” without feedback because:
- clustering outcomes are data-dependent
- “good” summaries depend on how extractive you want them
- retrieval quality depends on your QA model + prompt style

In this repo, we provide **heuristics + warnings** (safe) rather than pretending to guarantee an optimum.

## Summary profiles (one flag presets)
If you want “one setting that applies a bundle of per-layer summary defaults”, use:

- `--tb-summary-profile chapter-summary` (recommended)
  - Targets the hierarchy: **chapter → summary → bullets** at the top layers
  - Defaults roughly:
    - lengths: L1=200, L2=120, L3=80, L4=60
    - modes: L1/L2=`summary`, L3/L4=`bullets`

Other profiles:
- `--tb-summary-profile browse`: more aggressively “browsing friendly”
- `--tb-summary-profile rag`: richer summaries for retrieval

Important: **explicit flags override profiles**, e.g. `--tb-summary-profile chapter-summary --tb-summary-length-by-layer 3=120` will keep the profile but override L3 length.

