# `knowledge_base/` — IncidentFox Knowledge Base (RAPTOR) *(implemented)*

This subsystem provides **operational memory + retrieval** for IncidentFox. In the current port, it contains a full **RAPTOR** implementation (tree-organized retrieval) plus scripts and datasets (notably Kubernetes docs) to build and query retrieval trees.

How IncidentFox uses this:
- `ai_pipeline/` can build/update trees from ingested corpora (runbooks, postmortems, docs) and store artifacts (KB updates are part of the learning loop).
- `agent/` can query the tree during investigations to pull relevant context with better long-context behavior than flat chunk retrieval.
- `web_ui/` surfaces the **Tree Explorer** (interactive RAPTOR tree visualization, semantic search, Q&A with citations).

---

## RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="raptor_dark.png">
  <img alt="RAPTOR tree-organized retrieval diagram." src="raptor.jpg">
</picture>

**RAPTOR** introduces a novel approach to retrieval-augmented language models by constructing a recursive tree structure from documents. This allows for more efficient and context-aware information retrieval across large texts, addressing common limitations in traditional language models. 

For detailed methodologies and implementations, refer to the original paper:
- [RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval](https://arxiv.org/abs/2401.18059)

<!-- <picture>
  <source media="(prefers-color-scheme: dark)" srcset="raptor.jpg" width="1000px">
  <source media="(prefers-color-scheme: light)" srcset="raptor_dark.png" width="1000px">
  
</picture> -->

[![Paper page](https://huggingface.co/datasets/huggingface/badges/resolve/main/paper-page-sm.svg)](https://huggingface.co/papers/2401.18059)
[![PWC](https://img.shields.io/endpoint.svg?url=https://paperswithcode.com/badge/raptor-recursive-abstractive-processing-for/question-answering-on-quality)](https://paperswithcode.com/sota/question-answering-on-quality?p=raptor-recursive-abstractive-processing-for)

## Installation

Before using RAPTOR, ensure Python 3.8+ is installed. This code is part of a mono-repo structure. Navigate to the knowledge_base directory and install necessary dependencies:

```bash
cd knowledge_base  # or path/to/mono-repo/knowledge_base
pip install -r requirements.txt
```

**Note**: All scripts should be run from the `knowledge_base` directory root, and use `PYTHONPATH=.` when invoking scripts to ensure imports work correctly.

## Basic Usage

To get started with RAPTOR, follow these steps:

### Setting Up RAPTOR

First, set your OpenAI API key and initialize the RAPTOR configuration:

```python
import os
os.environ["OPENAI_API_KEY"] = "your-openai-api-key"

from raptor import RetrievalAugmentation

# Initialize with default configuration.
# For a practical parameter guide (chunking / layers / summarization length), see `docs/parameter_recommendations.md`.
RA = RetrievalAugmentation()
```

### Adding Documents to the Tree

Add your text documents to RAPTOR for indexing:

```python
with open('sample.txt', 'r') as file:
    text = file.read()
RA.add_documents(text)
```

### Answering Questions

You can now use RAPTOR to answer questions based on the indexed documents:

```python
question = "How did Cinderella reach her happy ending?"
answer = RA.answer_question(question=question)
print("Answer: ", answer)
```

### Saving and Loading the Tree

Save the constructed tree to a specified path:

```python
SAVE_PATH = "demo/cinderella"
RA.save(SAVE_PATH)
```

Load the saved tree back into RAPTOR:

```python
RA = RetrievalAugmentation(tree=SAVE_PATH)
answer = RA.answer_question(question=question)
```

## API Server

The knowledge base includes a FastAPI server (`api_server.py`) for programmatic access:

```bash
# Run the API server
cd knowledge_base
RAPTOR_TREES_DIR=./trees RAPTOR_DEFAULT_TREE=mega_ultra_v2 python api_server.py
```

### Core Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with loaded trees info |
| `/api/v1/trees` | GET | List available RAPTOR trees |
| `/api/v1/search` | POST | Semantic search across tree nodes |
| `/api/v1/answer` | POST | Q&A with citations from tree context |
| `/api/v1/retrieve` | POST | Retrieve relevant chunks only |

### Tree Explorer Endpoints (for web_ui)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/tree/stats` | GET | Node counts, layers, statistics |
| `/api/v1/tree/structure` | GET | Top N layers for visualization (lazy load) |
| `/api/v1/tree/nodes/{id}` | GET | Get node details |
| `/api/v1/tree/nodes/{id}/children` | GET | Get children for node expansion |
| `/api/v1/tree/nodes/{id}/text` | GET | Get full text content of a node |
| `/api/v1/tree/search-nodes` | POST | Search nodes for highlighting |

### Example: Ask a question

```bash
curl -X POST http://localhost:8000/api/v1/answer \
  -H "Content-Type: application/json" \
  -d '{"question": "How do I debug OOMKilled pods?", "tree": "mega_ultra_v2", "top_k": 5}'
```

## Build Flow / Architecture (quick map)

If you're new to the repo, this is the “main path” from raw text to a RAPTOR tree:

```text
scripts/ingest_k8s.py
  → RetrievalAugmentation.add_chunks(chunks)
    → TreeBuilder.build_from_chunks(chunks)
      → ClusterTreeBuilder.construct_tree(...)
        → RAPTOR_Clustering.perform_clustering(...)   (UMAP + GMM)
        → process_cluster(cluster)
          → get_text_for_summary(children)
          → TreeBuilder.summarize(context, layer=...)
          → create_node(index, summary, children=set(...))  # embeds summary
```

Outputs:
- **Tree**: a `Tree` object containing `Node`s (`raptor/tree_structures.py`)
- **Artifacts** (if using `scripts/ingest_k8s.py`): a `.pkl` tree file and optionally an interactive `.html` visualization

Key files to read:
- **Entry points**: `scripts/ingest_k8s.py`, `raptor/RetrievalAugmentation.py`
- **Tree building**: `raptor/tree_builder.py`, `raptor/cluster_tree_builder.py`
- **Clustering**: `raptor/cluster_utils.py`
- **Chunking + summary context cleaning**: `raptor/utils.py`
- **Summarization prompts/guards**: `raptor/SummarizationModels.py`

Diagram (conceptual):

```text
[docs/corpus] → [chunks] → [leaf embeddings] → [clusters] → [cluster summaries] → [parent embeddings] → … → [top layer]
```


### Extending RAPTOR with other Models

RAPTOR is designed to be flexible and allows you to integrate any models for summarization, question-answering (QA), and embedding generation. Here is how to extend RAPTOR with your own models:

#### Custom Summarization Model

If you wish to use a different language model for summarization, you can do so by extending the `BaseSummarizationModel` class. Implement the `summarize` method to integrate your custom summarization logic:

```python
from raptor import BaseSummarizationModel

class CustomSummarizationModel(BaseSummarizationModel):
    def __init__(self):
        # Initialize your model here
        pass

    def summarize(self, context, max_tokens=150):
        # Implement your summarization logic here
        # Return the summary as a string
        summary = "Your summary here"
        return summary
```

#### Custom QA Model

For custom QA models, extend the `BaseQAModel` class and implement the `answer_question` method. This method should return the best answer found by your model given a context and a question:

```python
from raptor import BaseQAModel

class CustomQAModel(BaseQAModel):
    def __init__(self):
        # Initialize your model here
        pass

    def answer_question(self, context, question):
        # Implement your QA logic here
        # Return the answer as a string
        answer = "Your answer here"
        return answer
```

#### Custom Embedding Model

To use a different embedding model, extend the `BaseEmbeddingModel` class. Implement the `create_embedding` method, which should return a vector representation of the input text:

```python
from raptor import BaseEmbeddingModel

class CustomEmbeddingModel(BaseEmbeddingModel):
    def __init__(self):
        # Initialize your model here
        pass

    def create_embedding(self, text):
        # Implement your embedding logic here
        # Return the embedding as a numpy array or a list of floats
        embedding = [0.0] * embedding_dim  # Replace with actual embedding logic
        return embedding
```

#### Integrating Custom Models with RAPTOR

After implementing your custom models, integrate them with RAPTOR as follows:

```python
from raptor import RetrievalAugmentation, RetrievalAugmentationConfig

# Initialize your custom models
custom_summarizer = CustomSummarizationModel()
custom_qa = CustomQAModel()
custom_embedding = CustomEmbeddingModel()

# Create a config with your custom models
custom_config = RetrievalAugmentationConfig(
    summarization_model=custom_summarizer,
    qa_model=custom_qa,
    embedding_model=custom_embedding
)

# Initialize RAPTOR with your custom config
RA = RetrievalAugmentation(config=custom_config)
```

Check out `demo.ipynb` for examples on how to specify your own summarization/QA models, such as Llama/Mistral/Gemma, and Embedding Models such as SBERT, for use with RAPTOR.

Note: More examples and ways to configure RAPTOR are forthcoming. Advanced usage and additional features will be provided in the documentation and repository updates.

## Contributing

RAPTOR is an open-source project, and contributions are welcome. Whether you're fixing bugs, adding new features, or improving documentation, your help is appreciated.

## License

RAPTOR is released under the MIT License. See the LICENSE file in the repository for full details.

## Citation

If RAPTOR assists in your research, please cite it as follows:

```bibtex
@inproceedings{sarthi2024raptor,
    title={RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval},
    author={Sarthi, Parth and Abdullah, Salman and Tuli, Aditi and Khanna, Shubh and Goldie, Anna and Manning, Christopher D.},
    booktitle={International Conference on Learning Representations (ICLR)},
    year={2024}
}
```

Stay tuned for more examples, configuration guides, and updates.
