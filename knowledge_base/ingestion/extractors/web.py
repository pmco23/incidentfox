"""Web scraping extractor using Playwright and BeautifulSoup."""

from __future__ import annotations

import hashlib
import time
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from ingestion.extractors.base import BaseExtractor
from ingestion.metadata import ExtractedContent, SourceMetadata


class WebExtractor(BaseExtractor):
    """Extract content from web pages."""

    def __init__(
        self,
        use_playwright: bool = True,
        timeout: int = 30,
        user_agent: Optional[str] = None,
        wait_for_selector: Optional[str] = None,
    ):
        """
        Initialize web extractor.

        Args:
            use_playwright: Use Playwright for JS-heavy sites (default: True)
            timeout: Request timeout in seconds
            user_agent: Custom user agent string
            wait_for_selector: CSS selector to wait for (Playwright only)
        """
        self.use_playwright = use_playwright
        self.timeout = timeout
        self.user_agent = (
            user_agent
            or "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        self.wait_for_selector = wait_for_selector

        if use_playwright:
            try:
                from playwright.sync_api import sync_playwright

                self.playwright = sync_playwright
            except ImportError:
                self.use_playwright = False

    def can_handle(self, source: str) -> bool:
        """Check if source is a URL."""
        try:
            result = urlparse(source)
            return result.scheme in ("http", "https")
        except Exception:
            return False

    def extract(self, source: str, **kwargs) -> ExtractedContent:
        """Extract content from a web page."""
        start_time = time.time()

        if self.use_playwright:
            content, metadata = self._extract_with_playwright(source, **kwargs)
        else:
            content, metadata = self._extract_with_requests(source, **kwargs)

        duration = time.time() - start_time
        metadata.processing_duration_seconds = duration
        metadata.processing_steps.append("web_extraction")

        return ExtractedContent(
            text=content,
            metadata=metadata,
        )

    def _extract_with_playwright(
        self, url: str, **kwargs
    ) -> tuple[str, SourceMetadata]:
        """Extract using Playwright (handles JavaScript)."""
        from playwright.sync_api import sync_playwright

        source_id = hashlib.sha1(url.encode()).hexdigest()
        metadata = SourceMetadata(
            source_type="web",
            source_url=url,
            source_id=source_id,
            ingested_at=datetime.utcnow(),
            original_format="html",
            mime_type="text/html",
            extraction_method="playwright_scraping",
        )

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_extra_http_headers({"User-Agent": self.user_agent})

            try:
                page.goto(url, wait_until="networkidle", timeout=self.timeout * 1000)

                if self.wait_for_selector:
                    page.wait_for_selector(self.wait_for_selector, timeout=10000)

                # Get page content
                html = page.content()

                # Extract text
                soup = BeautifulSoup(html, "lxml")
                # Remove script and style elements
                for script in soup(["script", "style", "nav", "footer", "header"]):
                    script.decompose()

                # Get text
                text = soup.get_text(separator="\n", strip=True)

                # Try to get title
                title_tag = soup.find("title")
                if title_tag:
                    title = title_tag.get_text()
                    text = f"# {title}\n\n{text}"

                # Extract metadata
                meta_desc = soup.find("meta", attrs={"name": "description"})
                if meta_desc and meta_desc.get("content"):
                    metadata.custom_metadata["description"] = meta_desc["content"]

                browser.close()
                return text, metadata

            except Exception as e:
                browser.close()
                raise Exception(f"Playwright extraction failed: {e}") from e

    def _extract_with_requests(self, url: str, **kwargs) -> tuple[str, SourceMetadata]:
        """Extract using requests + BeautifulSoup (faster, no JS)."""
        source_id = hashlib.sha1(url.encode()).hexdigest()
        metadata = SourceMetadata(
            source_type="web",
            source_url=url,
            source_id=source_id,
            ingested_at=datetime.utcnow(),
            original_format="html",
            mime_type="text/html",
            extraction_method="requests_scraping",
        )

        headers = {"User-Agent": self.user_agent}
        response = requests.get(url, headers=headers, timeout=self.timeout)

        response.raise_for_status()

        soup = BeautifulSoup(response.content, "lxml")

        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()

        # Get text
        text = soup.get_text(separator="\n", strip=True)

        # Try to get title
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text()
            text = f"# {title}\n\n{text}"

        # Extract metadata
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            metadata.custom_metadata["description"] = meta_desc["content"]

        return text, metadata
