"""arXiv abstract page extractor.

Uses the arXiv Atom API for structured paper metadata,
with HTML scraping as a fallback.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

from recursive_content_extractor.extractors.base import BaseExtractor
from recursive_content_extractor.models import ContentType, ExtractionResult

logger = logging.getLogger(__name__)

# Matches arxiv.org/abs/{paper_id} — new format, old format, versioned
_ABS_PATTERN = re.compile(
    r"^https?://(?:www\.)?arxiv\.org/abs/"
    r"(?P<paper_id>(?:\d{4}\.\d{4,5}|[a-z\-]+/\d{7})(?:v\d+)?)$"
)

# Atom namespace
_ATOM_NS = "{http://www.w3.org/2005/Atom}"
_ARXIV_NS = "{http://arxiv.org/schemas/atom}"


class ArXivExtractor(BaseExtractor):
    """Extracts metadata from arXiv abstract pages via the Atom API.

    Strategy order:
    1. arXiv Atom API (structured XML)
    2. HTML scraping (BeautifulSoup)

    Does NOT match arxiv.org/pdf/ URLs — those go to PDFExtractor.
    """

    @staticmethod
    def can_handle(url: str) -> bool:
        parsed = urlparse(url)
        domain = parsed.netloc.lower().removeprefix("www.")
        if domain != "arxiv.org":
            return False
        return bool(_ABS_PATTERN.match(url))

    @staticmethod
    def priority() -> int:
        return 45

    @staticmethod
    def _extract_paper_id(url: str) -> str | None:
        match = _ABS_PATTERN.match(url)
        return match.group("paper_id") if match else None

    async def extract(self, url: str) -> ExtractionResult:
        paper_id = self._extract_paper_id(url)
        if not paper_id:
            return ExtractionResult(
                url=url,
                content_type=ContentType.ERROR,
                content="[Could not parse arXiv URL]",
            )

        # Strategy 1: arXiv Atom API
        result = await self._try_api(url, paper_id)
        if result and result.content:
            return result

        # Strategy 2: HTML scraping
        result = await self._try_html(url, paper_id)
        if result and result.content:
            return result

        # All strategies failed
        logger.warning(f"All extraction strategies failed for {url}")
        return ExtractionResult(
            url=url,
            title=f"arXiv:{paper_id}",
            content=f"[Could not extract content from {url}]",
            content_type=ContentType.ARXIV,
            metadata={"paper_id": paper_id},
        )

    async def _try_api(self, original_url: str, paper_id: str) -> ExtractionResult | None:
        """Use arXiv Atom API for structured metadata."""
        client = await self._get_client()

        try:
            api_url = f"http://export.arxiv.org/api/query?id_list={paper_id}"
            resp = await client.get(api_url)
            if resp.status_code != 200:
                logger.debug(f"arXiv API returned {resp.status_code}")
                return None

            root = ET.fromstring(resp.text)
            entry = root.find(f"{_ATOM_NS}entry")
            if entry is None:
                return None

            # Check for error (arXiv returns an entry with id "http://arxiv.org/api/errors#...")
            entry_id = entry.findtext(f"{_ATOM_NS}id", "")
            if "errors" in entry_id:
                return None

            title = (entry.findtext(f"{_ATOM_NS}title", "") or "").strip()
            title = re.sub(r"\s+", " ", title)  # Collapse whitespace

            # Authors
            authors: list[str] = []
            for author_el in entry.findall(f"{_ATOM_NS}author"):
                name = author_el.findtext(f"{_ATOM_NS}name", "")
                if name:
                    authors.append(name.strip())

            # Abstract
            abstract = (entry.findtext(f"{_ATOM_NS}summary", "") or "").strip()
            abstract = re.sub(r"\s+", " ", abstract)

            # Published date
            published = entry.findtext(f"{_ATOM_NS}published", "")
            if published:
                published = published[:10]  # Just YYYY-MM-DD

            # Primary category
            primary_cat_el = entry.find(f"{_ARXIV_NS}primary_category")
            primary_category = ""
            if primary_cat_el is not None:
                primary_category = primary_cat_el.get("term", "")

            # DOI
            doi_el = entry.find(f"{_ARXIV_NS}doi")
            doi = doi_el.text.strip() if doi_el is not None and doi_el.text else ""

            # Journal ref
            journal_el = entry.find(f"{_ARXIV_NS}journal_ref")
            journal_ref = (
                journal_el.text.strip() if journal_el is not None and journal_el.text else ""
            )

            # Comment
            comment_el = entry.find(f"{_ARXIV_NS}comment")
            comment = comment_el.text.strip() if comment_el is not None and comment_el.text else ""

            # PDF link
            pdf_url = ""
            for link_el in entry.findall(f"{_ATOM_NS}link"):
                if link_el.get("title") == "pdf":
                    pdf_url = link_el.get("href", "")
                    break
            if not pdf_url:
                pdf_url = f"https://arxiv.org/pdf/{paper_id}"

            # Build formatted content
            parts: list[str] = []
            parts.append(f"# {title}")
            parts.append("")

            if authors:
                parts.append(f"**Authors:** {', '.join(authors)}")
            if primary_category:
                parts.append(f"**Primary Category:** {primary_category}")
            if published:
                parts.append(f"**Published:** {published}")
            if doi:
                parts.append(f"**DOI:** {doi}")
            if journal_ref:
                parts.append(f"**Journal:** {journal_ref}")
            if comment:
                parts.append(f"**Comment:** {comment}")

            parts.append("")
            parts.append("## Abstract")
            parts.append("")
            parts.append(abstract)

            content = "\n".join(parts)

            # Links for recursive extraction
            links: list[str] = []
            if pdf_url:
                links.append(pdf_url)
            if doi:
                links.append(f"https://doi.org/{doi}")

            return ExtractionResult(
                url=original_url,
                title=title,
                content=content[: self.config.max_content_length],
                content_type=ContentType.ARXIV,
                links=links,
                metadata={
                    "paper_id": paper_id,
                    "authors": authors,
                    "primary_category": primary_category,
                    "published": published,
                    "doi": doi,
                    "journal_ref": journal_ref,
                    "comment": comment,
                    "pdf_url": pdf_url,
                    "source": "arxiv_api",
                },
            )
        except Exception as e:
            logger.debug(f"arXiv API extraction failed: {e}")
            return None

    async def _try_html(self, original_url: str, paper_id: str) -> ExtractionResult | None:
        """Scrape the arXiv abstract page with BeautifulSoup."""
        from bs4 import BeautifulSoup

        client = await self._get_client()

        try:
            resp = await client.get(f"https://arxiv.org/abs/{paper_id}")
            if resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.text, "lxml")

            # Title
            title_el = soup.select_one("h1.title")
            title = ""
            if title_el:
                # Remove the "Title:" prefix span
                for span in title_el.find_all("span", class_="descriptor"):
                    span.decompose()
                title = title_el.get_text(strip=True)

            # Authors
            authors_el = soup.select_one("div.authors")
            authors_text = ""
            if authors_el:
                for span in authors_el.find_all("span", class_="descriptor"):
                    span.decompose()
                authors_text = authors_el.get_text(strip=True)

            # Abstract
            abstract_el = soup.select_one("blockquote.abstract")
            abstract = ""
            if abstract_el:
                for span in abstract_el.find_all("span", class_="descriptor"):
                    span.decompose()
                abstract = abstract_el.get_text(strip=True)

            if not title and not abstract:
                return None

            # Build content
            parts: list[str] = []
            if title:
                parts.append(f"# {title}")
                parts.append("")
            if authors_text:
                parts.append(f"**Authors:** {authors_text}")
                parts.append("")
            if abstract:
                parts.append("## Abstract")
                parts.append("")
                parts.append(abstract)

            content = "\n".join(parts)
            pdf_url = f"https://arxiv.org/pdf/{paper_id}"

            return ExtractionResult(
                url=original_url,
                title=title or f"arXiv:{paper_id}",
                content=content[: self.config.max_content_length],
                content_type=ContentType.ARXIV,
                links=[pdf_url],
                metadata={
                    "paper_id": paper_id,
                    "source": "html_scraping",
                },
            )
        except Exception as e:
            logger.debug(f"arXiv HTML scraping failed: {e}")
            return None
