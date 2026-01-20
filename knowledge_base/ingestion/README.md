# Multimodal Ingestion System

Production-grade ingestion system for the knowledge base, supporting multiple source types and multimodal content processing.

## Features

### Source Extractors
- **Web Scraping**: Extract content from web pages (Playwright or requests)
- **PDF Extraction**: Extract text, tables, and images from PDFs
- **File Extraction**: Support for text, DOCX, XLSX, CSV, JSON files
- **API Extractors**: Extract from REST/GraphQL APIs (GitHub, Slack, custom)
- **Database Extractors**: Extract from SQL and NoSQL databases

### Multimodal Processors
- **Image Processing**: GPT-4 Vision for OCR and image description
- **Audio Processing**: Whisper API for speech-to-text transcription
- **Video Processing**: Extract audio + key frames for comprehensive processing

### Metadata Preservation
- Rich metadata tracking (source type, processing steps, costs, timestamps)
- Full provenance chain (parent-child relationships)
- Quality metrics (confidence scores, language detection)

### Production Features
- Cost tracking and reporting
- Rate limiting for API calls
- Error handling and fallbacks
- Batch processing support

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (optional, for JS-heavy sites)
playwright install
```

## Quick Start

### Basic Usage

```python
from ingestion import IngestionOrchestrator

# Initialize orchestrator
orchestrator = IngestionOrchestrator(
    openai_api_key="your-api-key",  # Required for multimodal
    enable_multimodal=True,
)

# Ingest a single source
content = orchestrator.ingest("https://example.com/article")

# Ingest multiple sources
contents = orchestrator.ingest_batch([
    "https://example.com/article1",
    "path/to/document.pdf",
    "path/to/image.png",
])

# Write to corpus JSONL (compatible with RAPTOR)
orchestrator.ingest_to_corpus(
    sources=["https://example.com"],
    output_path=Path("corpus.jsonl"),
)
```

### CLI Usage

```bash
# Ingest sources and build RAPTOR tree
python scripts/ingest_multimodal.py \
    --sources "https://example.com" "path/to/file.pdf" \
    --output-corpus datasources/ingested/corpus.jsonl \
    --build-tree \
    --output-tree datasources/ingested/tree.pkl

# Disable multimodal processing (text-only)
python scripts/ingest_multimodal.py \
    --sources "https://example.com" \
    --no-multimodal \
    --output-corpus corpus.jsonl
```

## Architecture

```
┌─────────────────────────────────────────┐
│     IngestionOrchestrator               │
│  (Main entry point)                     │
└─────────────────────────────────────────┘
            │
    ┌───────┴───────┐
    │               │
    ▼               ▼
┌─────────┐   ┌──────────┐
│Extractors│   │Processors│
└─────────┘   └──────────┘
    │               │
    ▼               ▼
┌─────────────────────────┐
│   ExtractedContent      │
│   (with metadata)       │
└─────────────────────────┘
            │
            ▼
┌─────────────────────────┐
│   Corpus JSONL          │
│   (RAPTOR compatible)   │
└─────────────────────────┘
```

## Cost Tracking

The system automatically tracks API costs:

```python
from ingestion.cost_tracker import CostTracker

tracker = CostTracker(log_file=Path("costs.jsonl"))

# Costs are automatically recorded during processing
# View summary
summary = tracker.get_summary()
print(f"Total cost: ${summary['total_cost_usd']:.4f}")
print(f"By operation: {summary['by_operation']}")
```

## Rate Limiting

Rate limiting is built-in to prevent API quota exhaustion:

```python
from ingestion.rate_limiter import RateLimiter

limiter = RateLimiter(
    requests_per_minute=60,
    requests_per_hour=1000,
)

# Use before API calls
limiter.wait_if_needed("openai_api")
```

## Supported Sources

### Web URLs
```python
orchestrator.ingest("https://example.com/article")
```

### Files
```python
orchestrator.ingest("path/to/document.pdf")
orchestrator.ingest("path/to/image.png")
orchestrator.ingest("path/to/video.mp4")
orchestrator.ingest("path/to/audio.wav")
```

### APIs
```python
from ingestion.extractors import GitHubExtractor

github = GitHubExtractor(auth_token="your-token")
content = github.extract_repo_file("owner", "repo", "path/to/file.md")
```

### Databases
```python
from ingestion.extractors import DatabaseExtractor

db = DatabaseExtractor(
    db_type="postgresql",
    connection_string="postgresql://user:pass@host/db",
    query="SELECT * FROM documents",
)
content = db.extract("postgresql://...")
```

## Multimodal Processing

### Images
- Automatically detects images in PDFs, web pages, or direct file paths
- Uses GPT-4 Vision for OCR and description
- Falls back to pytesseract if GPT-4 unavailable

### Audio
- Supports MP3, WAV, M4A, OGG, FLAC
- Uses Whisper API for transcription
- Includes timestamps and confidence scores

### Video
- Extracts audio track for transcription
- Samples key frames for visual description
- Combines audio + visual information

## Metadata

Every ingested item includes rich metadata:

```python
content.metadata.source_type  # "web", "pdf", "video", etc.
content.metadata.processing_steps  # ["web_extraction", "image_processing"]
content.metadata.processing_cost_usd  # 0.025
content.metadata.processing_duration_seconds  # 2.5
content.metadata.language  # "en"
content.metadata.tags  # ["tutorial", "kubernetes"]
```

## Integration with RAPTOR

The ingestion system outputs corpus JSONL files that are fully compatible with existing RAPTOR tree building:

```python
# Ingest and build tree in one step
python scripts/ingest_multimodal.py \
    --sources "https://example.com" \
    --build-tree \
    --output-tree tree.pkl

# Or use existing RAPTOR tools
python scripts/ingest_k8s.py --corpus corpus.jsonl --out-tree tree.pkl
```

## Error Handling

The system includes robust error handling:
- Automatic fallbacks (e.g., OCR if GPT-4 Vision fails)
- Graceful degradation (skip multimodal if API unavailable)
- Detailed error logging
- Batch processing continues on individual failures

## Performance

- **Web scraping**: ~0.5-2s per page (requests) or 2-5s (Playwright)
- **PDF extraction**: ~0.1-1s per page
- **Image processing**: ~1-3s per image (GPT-4 Vision)
- **Audio transcription**: ~real-time (Whisper API)
- **Video processing**: ~10-30s per minute of video

## Cost Estimates

- **Web scraping**: Free (self-hosted) or $0.001-0.01/page (services)
- **PDF extraction**: Free (open source tools)
- **Image processing**: $0.01-0.03 per image (GPT-4 Vision)
- **Audio transcription**: $0.006 per minute (Whisper API)
- **Video processing**: ~$0.16-0.36 per 10-minute video

## Examples

See `scripts/validate_ingestion.py` for validation examples and `scripts/ingest_multimodal.py` for CLI usage.

## Production Deployment

For production use:
1. Set up environment variables (OPENAI_API_KEY, etc.)
2. Configure rate limits based on API quotas
3. Set up cost tracking and monitoring
4. Use batch processing for large-scale ingestion
5. Monitor processing times and costs

## License

Part of the knowledge_base subsystem. See main LICENSE file.

