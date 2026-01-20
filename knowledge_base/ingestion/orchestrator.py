"""
Ingestion orchestrator - coordinates extractors and processors.

This is the main entry point for the ingestion pipeline.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Optional

from ingestion.extractors import (
    APIExtractor,
    BaseExtractor,
    DatabaseExtractor,
    FileExtractor,
    PDFExtractor,
    WebExtractor,
)
from ingestion.metadata import ExtractedContent
from ingestion.processors import (
    AudioProcessor,
    BaseProcessor,
    ImageProcessor,
    VideoProcessor,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IngestionOrchestrator:
    """Orchestrates the ingestion pipeline."""

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        enable_multimodal: bool = True,
        storage_dir: Optional[Path] = None,
    ):
        """
        Initialize orchestrator.

        Args:
            openai_api_key: OpenAI API key for multimodal processing
            enable_multimodal: Enable image/audio/video processing
            storage_dir: Directory to store extracted assets
        """
        self.openai_api_key = openai_api_key
        self.enable_multimodal = enable_multimodal
        self.storage_dir = storage_dir or Path("/tmp/ingestion_storage")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Initialize extractors
        # Use requests by default (faster, no browser needed)
        # Playwright can be enabled if needed for JS-heavy sites
        self.extractors: List[BaseExtractor] = [
            WebExtractor(use_playwright=False),  # Use requests by default
            PDFExtractor(extract_images=True, extract_tables=True),
            FileExtractor(),
            APIExtractor(),
            DatabaseExtractor(db_type="postgresql"),  # Will be configured per-use
        ]

        # Initialize processors
        self.processors: List[BaseProcessor] = []
        if enable_multimodal:
            self.processors = [
                ImageProcessor(openai_api_key=openai_api_key),
                AudioProcessor(openai_api_key=openai_api_key),
                VideoProcessor(openai_api_key=openai_api_key),
            ]

    def ingest(self, source: str, **kwargs) -> ExtractedContent:
        """
        Ingest content from a source.

        Args:
            source: Source identifier (URL, file path, etc.)
            **kwargs: Additional parameters for extractors/processors

        Returns:
            ExtractedContent ready for RAPTOR tree building
        """
        logger.info(f"Ingesting source: {source}")

        # Find appropriate extractor
        extractor = self._find_extractor(source)
        if not extractor:
            raise ValueError(f"No extractor found for source: {source}")

        # Extract content
        logger.info(f"Using extractor: {extractor.__class__.__name__}")
        content = extractor.extract(source, **kwargs)

        # Process with multimodal processors if needed
        if self.enable_multimodal:
            content = self._process_content(content)

        logger.info(f"Ingestion complete: {content.metadata.source_id}")
        return content

    def ingest_batch(self, sources: List[str], **kwargs) -> List[ExtractedContent]:
        """
        Ingest multiple sources.

        Args:
            sources: List of source identifiers
            **kwargs: Additional parameters

        Returns:
            List of ExtractedContent
        """
        results = []
        for source in sources:
            try:
                content = self.ingest(source, **kwargs)
                results.append(content)
            except Exception as e:
                logger.error(f"Failed to ingest {source}: {e}")
                # Continue with other sources
        return results

    def ingest_to_corpus(
        self,
        sources: List[str],
        output_path: Path,
        **kwargs,
    ) -> Path:
        """
        Ingest sources and write to corpus JSONL file (compatible with RAPTOR).

        Args:
            sources: List of source identifiers
            output_path: Path to output JSONL file
            **kwargs: Additional parameters

        Returns:
            Path to output file
        """
        contents = self.ingest_batch(sources, **kwargs)

        # Write to JSONL
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for content in contents:
                record = content.to_corpus_record()
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        logger.info(f"Wrote {len(contents)} records to {output_path}")
        return output_path

    def _find_extractor(self, source: str) -> Optional[BaseExtractor]:
        """Find appropriate extractor for source."""
        for extractor in self.extractors:
            if extractor.can_handle(source):
                return extractor
        return None

    def _process_content(self, content: ExtractedContent) -> ExtractedContent:
        """Process content with multimodal processors."""
        for processor in self.processors:
            if processor.can_process(content):
                logger.info(f"Processing with: {processor.__class__.__name__}")
                try:
                    content = processor.process(content)
                except Exception as e:
                    logger.warning(
                        f"Processor {processor.__class__.__name__} failed: {e}"
                    )
                    # Continue with other processors
        return content

    def add_extractor(self, extractor: BaseExtractor):
        """Add a custom extractor."""
        self.extractors.append(extractor)

    def add_processor(self, processor: BaseProcessor):
        """Add a custom processor."""
        self.processors.append(processor)
