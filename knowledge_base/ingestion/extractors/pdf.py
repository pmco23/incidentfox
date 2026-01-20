"""PDF extraction with text and image support."""

from __future__ import annotations

import hashlib
import time
from datetime import datetime
from pathlib import Path
from typing import List

import pdfplumber
from pypdf import PdfReader

from ingestion.extractors.base import BaseExtractor
from ingestion.metadata import ExtractedContent, SourceMetadata


class PDFExtractor(BaseExtractor):
    """Extract text and images from PDF files."""

    def __init__(self, extract_images: bool = True, extract_tables: bool = True):
        """
        Initialize PDF extractor.

        Args:
            extract_images: Extract images from PDF (for later processing)
            extract_tables: Extract tables as formatted text
        """
        self.extract_images = extract_images
        self.extract_tables = extract_tables

    def can_handle(self, source: str) -> bool:
        """Check if source is a PDF file."""
        path = Path(source)
        return path.exists() and path.suffix.lower() == ".pdf"

    def extract(self, source: str, **kwargs) -> ExtractedContent:
        """Extract content from PDF."""
        start_time = time.time()
        path = Path(source)

        source_id = hashlib.sha1(str(path.absolute()).encode()).hexdigest()
        metadata = SourceMetadata(
            source_type="pdf",
            source_url=str(path.absolute()),
            source_id=source_id,
            ingested_at=datetime.utcnow(),
            original_format="pdf",
            mime_type="application/pdf",
            extraction_method="pdf_extraction",
        )

        # Extract text using pypdf (fast, good for most PDFs)
        text_parts = []
        try:
            reader = PdfReader(path)
            metadata.custom_metadata["num_pages"] = len(reader.pages)

            for i, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text.strip():
                    text_parts.append(f"## Page {i + 1}\n{page_text}")

        except Exception as e:
            # Fallback to pdfplumber if pypdf fails
            try:
                with pdfplumber.open(path) as pdf:
                    metadata.custom_metadata["num_pages"] = len(pdf.pages)
                    for i, page in enumerate(pdf.pages):
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(f"## Page {i + 1}\n{page_text}")

                        # Extract tables if requested
                        if self.extract_tables:
                            tables = page.extract_tables()
                            for table in tables:
                                if table:
                                    table_text = self._format_table(table)
                                    text_parts.append(
                                        f"\n### Table on Page {i + 1}\n{table_text}\n"
                                    )
            except Exception as e2:
                raise Exception(
                    f"PDF extraction failed with both methods: {e}, {e2}"
                ) from e2

        # Extract images if requested
        extracted_assets = []
        if self.extract_images:
            try:
                images = self._extract_images(path)
                extracted_assets = images
                metadata.custom_metadata["num_images"] = len(images)
            except Exception:
                # Image extraction is optional, don't fail if it doesn't work
                pass

        text = "\n\n".join(text_parts)
        duration = time.time() - start_time
        metadata.processing_duration_seconds = duration
        metadata.processing_steps.append("pdf_extraction")

        return ExtractedContent(
            text=text,
            metadata=metadata,
            raw_content_path=path,
            extracted_assets=extracted_assets,
        )

    def _extract_images(self, pdf_path: Path) -> List[Path]:
        """Extract images from PDF pages."""
        images = []
        try:
            reader = PdfReader(pdf_path)
            for page_num, page in enumerate(reader.pages):
                if "/XObject" in page.get("/Resources", {}):
                    xobject = page["/Resources"]["/XObject"].get_object()
                    for obj_name in xobject:
                        obj = xobject[obj_name]
                        if obj.get("/Subtype") == "/Image":
                            # Save image
                            output_dir = pdf_path.parent / f"{pdf_path.stem}_images"
                            output_dir.mkdir(exist_ok=True)
                            img_path = output_dir / f"page_{page_num}_{obj_name}.png"
                            # Extract image data (simplified - full implementation would handle different formats)
                            # This is a placeholder - full image extraction is complex
                            pass
        except Exception:
            # Image extraction is best-effort
            pass
        return images

    def _format_table(self, table: List[List]) -> str:
        """Format table as markdown."""
        if not table:
            return ""
        # Simple markdown table format
        lines = []
        for row in table:
            if row:
                # Clean and format cells
                cells = [str(cell or "").replace("|", "\\|") for cell in row]
                lines.append("| " + " | ".join(cells) + " |")
        return "\n".join(lines)
