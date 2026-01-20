# Knowledge Base - RAPTOR Overview

RAPTOR (Recursive Abstractive Processing for Tree-Organized Retrieval) hierarchical knowledge base.

---

## What is RAPTOR?

A tree-structured knowledge base that organizes information hierarchically:

```
Layer 5: Top-level summaries (25 nodes)
   ↓
Layer 4: Fourth-level summaries (80 nodes)
   ↓
Layer 3: Third-level summaries (246 nodes)
   ↓
Layer 2: Second-level summaries (1,802 nodes)
   ↓
Layer 1: First-level summaries (13,422 nodes)
   ↓
Layer 0: Leaf nodes - source documents (39,023 nodes)

Total: 54,598 nodes
```

**Benefits**:
- Fast retrieval at any abstraction level
- Better context for LLM queries
- Hierarchical browsing (drill down from high-level to specific)

---

## Current Tree: mega_ultra_v2

**Source**: Kubernetes documentation

**Storage**: S3 bucket `s3://raptor-kb-trees-103002841599/trees/mega_ultra_v2/`

**Format**: Pickled Python object (tree.pkl)

---

## API

FastAPI server exposing tree operations:

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/tree/stats` | Get tree statistics |
| `GET /api/v1/tree/structure` | Get tree structure (for visualization) |
| `POST /api/v1/answer` | Query tree with LLM |
| `GET /api/v1/search` | Search nodes by keywords |

---

## Web UI Integration

The Web UI has a tree explorer at `/team/knowledge`:

- Visual tree navigation (React Flow)
- Node drill-down
- Search and filtering
- LLM-powered Q&A

See: `web_ui/src/components/knowledge/TreeExplorer.tsx`

---

## Deployment Options

- **Option A**: Kubernetes (recommended for customers)
- **Option B**: ECS Fargate (current IncidentFox deployment)

See: `/knowledge_base/docs/DEPLOYMENT_OPTIONS.md`

---

## Adding New Trees

1. Ingest source documents: `knowledge_base/ingestion/`
2. Build tree: `python ingestion/build_tree.py`
3. Upload to S3: `aws s3 cp tree.pkl s3://bucket/trees/new-tree/`
4. Deploy with new tree name

---

## Related Documentation

- `/knowledge_base/docs/DEPLOYMENT_OPTIONS.md` - Deployment guide
- `/knowledge_base/docs/DEPLOYMENT_STATUS.md` - Current status
- `/knowledge_base/docs/parameter_recommendations.md` - RAPTOR tuning
