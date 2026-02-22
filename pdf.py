"""PDF document extractor.

Downloads PDF files and extracts text content using PyMuPDF (fitz).
Also extracts hyperlinks embedded in the PDF.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import httpx

from extractors import BaseExtractor
from models import ContentType, ExtractionResult, ExtractorConfig

logger = logging.getLogger(__name__)


class PDFExtractor(BaseExtractor):
    """Extracts text and links from PDF documents."""

    def __init__(self, config: ExtractorConfig | None = None):
        super().__init__(config)
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.config.timeout,
                headers={"User-Agent": self.config.user_agent},
                follow_redirects=True,
            )
        return self._client

    @staticmethod
    def can_handle(url: str) -> bool:
        """Handles URLs ending in .pdf or known PDF hosts."""
        lower = url.lower().split("?")[0].split("#")[0]
        if lower.endswith(".pdf"):
            return True
        # Common PDF hosting patterns
        pdf_hosts = ["arxiv.org/pdf/", "papers.ssrn.com", "dl.acm.org/doi/pdf"]
        return any(host in lower for host in pdf_hosts)

    @staticmethod
    def priority() -> int:
        return 40

    async def extract(self, url: str) -> ExtractionResult:
        try:
            import fitz  # PyMuPDF
        except ImportError:
            return ExtractionResult(
                url=url,
                content_type=ContentType.PDF,
                content="[PyMuPDF (fitz) not installed. Run: pip install pymupdf]",
                metadata={"error": "pymupdf_not_installed"},
            )

        client = await self._get_client()

        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            return ExtractionResult(
                url=url,
                content_type=ContentType.ERROR,
                content=f"[Failed to download PDF: {e}]",
                metadata={"error": str(e)},
            )

        # Write to temp file and extract
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(resp.content)
            tmp_path = tmp.name

        try:
            doc = fitz.open(tmp_path)

            # Extract text
            text_parts = []
            links = []

            for page_num, page in enumerate(doc):
                text = page.get_text()
                if text.strip():
                    text_parts.append(f"--- Page {page_num + 1} ---\n{text}")

                # Extract hyperlinks from annotations
                for link in page.get_links():
                    uri = link.get("uri", "")
                    if uri and uri.startswith("http"):
                        links.append(uri)

            doc.close()

            content = "\n\n".join(text_parts)
            title = self._extract_title(content)

            # Extract metadata
            metadata_dict = {}
            try:
                doc = fitz.open(tmp_path)
                meta = doc.metadata
                if meta:
                    metadata_dict = {
                        k: v for k, v in meta.items() if v
                    }
                doc.close()
            except Exception:
                pass

            return ExtractionResult(
                url=url,
                title=title or f"PDF: {url.split('/')[-1]}",
                content=content[: self.config.max_content_length],
                content_type=ContentType.PDF,
                links=list(set(links)),
                metadata=metadata_dict,
            )

        except Exception as e:
            logger.error(f"PDF extraction failed for {url}: {e}")
            return ExtractionResult(
                url=url,
                content_type=ContentType.ERROR,
                content=f"[PDF extraction error: {e}]",
                metadata={"error": str(e)},
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def _extract_title(self, content: str) -> str:
        """Try to extract a title from the first lines of PDF text."""
        lines = content.split("\n")
        for line in lines[:10]:
            stripped = line.strip().strip("-— ")
            if stripped and len(stripped) > 5 and not stripped.startswith("Page"):
                return stripped[:200]
        return ""

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
