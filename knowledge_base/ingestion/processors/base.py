"""Base classes for processors."""

from abc import ABC, abstractmethod

from ingestion.metadata import ExtractedContent


class BaseProcessor(ABC):
    """Base class for all content processors."""

    @abstractmethod
    def process(self, content: ExtractedContent, **kwargs) -> ExtractedContent:
        """
        Process content to extract/convert to text.

        Args:
            content: ExtractedContent to process
            **kwargs: Processor-specific parameters

        Returns:
            Enhanced ExtractedContent with processed text
        """
        pass

    @abstractmethod
    def can_process(self, content: ExtractedContent) -> bool:
        """
        Check if this processor can handle the given content.

        Args:
            content: ExtractedContent to check

        Returns:
            True if this processor can handle the content
        """
        pass
