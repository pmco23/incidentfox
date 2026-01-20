"""
Metadata models for ingestion pipeline.

Preserves rich source information throughout the ingestion and tree-building process.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def _sha1(s: str) -> str:
    """Generate SHA1 hash for stable IDs."""
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


@dataclass
class SourceMetadata:
    """Rich metadata preserved throughout ingestion pipeline."""

    # Source identification (required fields first)
    source_type: (
        str  # "web", "pdf", "video", "audio", "image", "api", "slack", "database", etc.
    )
    source_url: str
    source_id: str  # Stable identifier (hash or UUID)
    ingested_at: datetime
    original_format: str  # "mp4", "pdf", "png", "markdown", etc.

    # Optional fields (with defaults)
    source_created_at: Optional[datetime] = None
    source_modified_at: Optional[datetime] = None
    mime_type: str = ""

    # Processing pipeline
    processing_steps: List[str] = field(
        default_factory=list
    )  # ["download", "transcribe", "ocr", "summarize"]
    processing_model: Optional[str] = None  # "whisper-large-v3", "gpt-4-vision", etc.
    processing_cost_usd: Optional[float] = None
    processing_duration_seconds: Optional[float] = None

    # Provenance
    parent_source_id: Optional[str] = (
        None  # For derived content (e.g., video → transcript)
    )
    extraction_method: str = "unknown"  # "scraping", "api", "manual_upload", etc.

    # Quality/Confidence
    confidence_score: Optional[float] = None  # For OCR/transcription confidence
    language: Optional[str] = None  # Detected language

    # Access control and organization
    access_level: str = "public"
    tags: List[str] = field(default_factory=list)

    # Additional custom metadata
    custom_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            "source_type": self.source_type,
            "source_url": self.source_url,
            "source_id": self.source_id,
            "ingested_at": self.ingested_at.isoformat(),
            "source_created_at": (
                self.source_created_at.isoformat() if self.source_created_at else None
            ),
            "source_modified_at": (
                self.source_modified_at.isoformat() if self.source_modified_at else None
            ),
            "original_format": self.original_format,
            "mime_type": self.mime_type,
            "processing_steps": self.processing_steps,
            "processing_model": self.processing_model,
            "processing_cost_usd": self.processing_cost_usd,
            "processing_duration_seconds": self.processing_duration_seconds,
            "parent_source_id": self.parent_source_id,
            "extraction_method": self.extraction_method,
            "confidence_score": self.confidence_score,
            "language": self.language,
            "access_level": self.access_level,
            "tags": self.tags,
            "custom_metadata": self.custom_metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SourceMetadata:
        """Deserialize from dictionary."""
        return cls(
            source_type=data["source_type"],
            source_url=data["source_url"],
            source_id=data["source_id"],
            ingested_at=datetime.fromisoformat(data["ingested_at"]),
            source_created_at=(
                datetime.fromisoformat(data["source_created_at"])
                if data.get("source_created_at")
                else None
            ),
            source_modified_at=(
                datetime.fromisoformat(data["source_modified_at"])
                if data.get("source_modified_at")
                else None
            ),
            original_format=data["original_format"],
            mime_type=data.get("mime_type", ""),
            processing_steps=data.get("processing_steps", []),
            processing_model=data.get("processing_model"),
            processing_cost_usd=data.get("processing_cost_usd"),
            processing_duration_seconds=data.get("processing_duration_seconds"),
            parent_source_id=data.get("parent_source_id"),
            extraction_method=data.get("extraction_method", "unknown"),
            confidence_score=data.get("confidence_score"),
            language=data.get("language"),
            access_level=data.get("access_level", "public"),
            tags=data.get("tags", []),
            custom_metadata=data.get("custom_metadata", {}),
        )


@dataclass
class ExtractedContent:
    """Content extracted from a source, ready for processing."""

    text: str  # Primary text content
    metadata: SourceMetadata
    raw_content_path: Optional[Path] = None  # Path to original file if stored locally
    additional_texts: Dict[str, str] = field(
        default_factory=dict
    )  # e.g., {"transcript": "...", "visual_summary": "..."}
    extracted_assets: List[Path] = field(
        default_factory=list
    )  # Images, audio files extracted from source

    def get_combined_text(self) -> str:
        """Get all text content combined."""
        parts = [self.text]
        if self.additional_texts:
            for key, value in self.additional_texts.items():
                parts.append(f"\n\n## {key.replace('_', ' ').title()}\n{value}")
        return "\n".join(parts)

    def to_corpus_record(self) -> Dict[str, Any]:
        """Convert to corpus JSONL format compatible with existing RAPTOR pipeline."""
        combined_text = self.get_combined_text()
        return {
            "id": self.metadata.source_id,
            "rel_path": self.metadata.source_url.replace("://", "_").replace("/", "_"),
            "source_url": self.metadata.source_url,
            "text": combined_text,
            "metadata": self.metadata.to_dict(),
        }
