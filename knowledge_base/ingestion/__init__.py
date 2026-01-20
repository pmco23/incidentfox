"""
Multimodal ingestion system for knowledge base.

This module provides production-grade ingestion capabilities for:
- Web scraping
- File extraction (PDF, DOCX, images, etc.)
- Multimodal processing (images, audio, video)
- API integrations
- Database extraction
"""

from ingestion.metadata import ExtractedContent, SourceMetadata
from ingestion.orchestrator import IngestionOrchestrator

__all__ = [
    "SourceMetadata",
    "ExtractedContent",
    "IngestionOrchestrator",
]
