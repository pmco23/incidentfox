#!/usr/bin/env python3
"""
Validate ingestion system with real API calls.

Tests extractors and processors with actual sources.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion import IngestionOrchestrator
from ingestion.extractors import FileExtractor, WebExtractor


def test_web_extractor():
    """Test web extractor with a real URL."""
    print("\n=== Testing Web Extractor ===")
    extractor = WebExtractor(use_playwright=False)  # Use requests for speed

    test_url = "https://en.wikipedia.org/wiki/Kubernetes"
    print(f"Extracting from: {test_url}")

    try:
        content = extractor.extract(test_url)
        print("✓ Success!")
        print(f"  Source ID: {content.metadata.source_id}")
        print(f"  Text length: {len(content.text)} chars")
        print(f"  Processing time: {content.metadata.processing_duration_seconds:.2f}s")
        print(f"  First 200 chars: {content.text[:200]}...")
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_file_extractor():
    """Test file extractor with a text file."""
    print("\n=== Testing File Extractor ===")
    extractor = FileExtractor()

    # Use existing demo file
    test_file = Path("demo/sample.txt")
    if not test_file.exists():
        print(f"✗ Test file not found: {test_file}")
        return False

    print(f"Extracting from: {test_file}")

    try:
        content = extractor.extract(str(test_file))
        print("✓ Success!")
        print(f"  Source ID: {content.metadata.source_id}")
        print(f"  Text length: {len(content.text)} chars")
        print(f"  First 200 chars: {content.text[:200]}...")
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_image_processor():
    """Test image processor with GPT-4 Vision."""
    print("\n=== Testing Image Processor ===")

    if not os.environ.get("OPENAI_API_KEY"):
        print("✗ OPENAI_API_KEY not set, skipping image processor test")
        return None

    from ingestion.processors import ImageProcessor

    processor = ImageProcessor()

    # Try to find an image file
    test_image = None
    for ext in [".png", ".jpg", ".jpeg"]:
        for path in Path(".").rglob(f"*{ext}"):
            if path.stat().st_size < 5 * 1024 * 1024:  # < 5MB
                test_image = path
                break
        if test_image:
            break

    if not test_image:
        print("✗ No suitable test image found")
        return None

    print(f"Processing image: {test_image}")

    import hashlib
    from datetime import datetime

    from ingestion.metadata import ExtractedContent, SourceMetadata

    metadata = SourceMetadata(
        source_type="image",
        source_url=str(test_image.absolute()),
        source_id=hashlib.sha1(str(test_image.absolute()).encode()).hexdigest(),
        ingested_at=datetime.utcnow(),
        original_format=test_image.suffix.lstrip("."),
        mime_type=f"image/{test_image.suffix.lstrip('.')}",
        extraction_method="file",
    )

    content = ExtractedContent(
        text=f"[Image: {test_image.name}]",
        metadata=metadata,
        raw_content_path=test_image,
    )

    try:
        processed = processor.process(content)
        print("✓ Success!")
        print(f"  Processing model: {processed.metadata.processing_model}")
        print(f"  Estimated cost: ${processed.metadata.processing_cost_usd:.4f}")
        print(
            f"  Processing time: {processed.metadata.processing_duration_seconds:.2f}s"
        )
        print(f"  Description length: {len(processed.text)} chars")
        print(f"  First 300 chars: {processed.text[:300]}...")
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_orchestrator():
    """Test full orchestrator."""
    print("\n=== Testing Ingestion Orchestrator ===")

    orchestrator = IngestionOrchestrator(
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
        enable_multimodal=bool(os.environ.get("OPENAI_API_KEY")),
    )

    # Test with a simple web URL
    test_sources = ["https://en.wikipedia.org/wiki/Kubernetes"]
    print(f"Ingesting {len(test_sources)} source(s)...")

    try:
        contents = orchestrator.ingest_batch(test_sources)
        print(f"✓ Success! Ingested {len(contents)} source(s)")

        for content in contents:
            print(f"  - {content.metadata.source_url}")
            print(f"    Type: {content.metadata.source_type}")
            print(f"    Text length: {len(content.text)} chars")
            print(f"    Processing steps: {content.metadata.processing_steps}")

        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all validation tests."""
    print("=" * 60)
    print("Ingestion System Validation")
    print("=" * 60)

    results = {}

    # Test extractors
    results["web_extractor"] = test_web_extractor()
    results["file_extractor"] = test_file_extractor()

    # Test processors (requires API key)
    results["image_processor"] = test_image_processor()

    # Test orchestrator
    results["orchestrator"] = test_orchestrator()

    # Summary
    print("\n" + "=" * 60)
    print("Validation Summary")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v is True)
    skipped = sum(1 for v in results.values() if v is None)
    failed = sum(1 for v in results.values() if v is False)

    for test, result in results.items():
        if result is True:
            print(f"✓ {test}: PASSED")
        elif result is None:
            print(f"⊘ {test}: SKIPPED")
        else:
            print(f"✗ {test}: FAILED")

    print(f"\nTotal: {passed} passed, {skipped} skipped, {failed} failed")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
