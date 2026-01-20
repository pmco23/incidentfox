"""Base classes for extractors."""

from abc import ABC, abstractmethod
from pathlib import Path

from ingestion.metadata import ExtractedContent


class BaseExtractor(ABC):
    """Base class for all source extractors."""

    @abstractmethod
    def extract(self, source: str, **kwargs) -> ExtractedContent:
        """
        Extract content from a source.

        Args:
            source: Source identifier (URL, file path, etc.)
            **kwargs: Additional extractor-specific parameters

        Returns:
            ExtractedContent with text and metadata
        """
        pass

    @abstractmethod
    def can_handle(self, source: str) -> bool:
        """
        Check if this extractor can handle the given source.

        Args:
            source: Source identifier

        Returns:
            True if this extractor can handle the source
        """
        pass

    def _detect_mime_type(self, file_path: Path) -> str:
        """Detect MIME type of a file."""
        try:
            import magic

            mime = magic.Magic(mime=True)
            return mime.from_file(str(file_path))
        except Exception:
            # Fallback to extension-based detection
            ext = file_path.suffix.lower()
            mime_map = {
                ".pdf": "application/pdf",
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".gif": "image/gif",
                ".mp4": "video/mp4",
                ".mp3": "audio/mpeg",
                ".wav": "audio/wav",
                ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ".txt": "text/plain",
                ".md": "text/markdown",
            }
            return mime_map.get(ext, "application/octet-stream")
