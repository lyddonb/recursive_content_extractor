"""Generic article/web page extractor.

Uses trafilatura for main content extraction and BeautifulSoup
for link discovery, including embedded tweets, iframes, and other
embedded content URLs.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

try:
    import trafilatura
except ImportError:
    trafilatura = None  # type: ignore[assignment]

from recursive_content_extractor.extractors.base import BaseExtractor
from recursive_content_extractor.models import ContentType, ExtractionResult

logger = logging.getLogger(__name__)

# Patterns for embedded content we want to extract URLs from
EMBED_PATTERNS = {
    # X/Twitter embeds
    "x_embed": re.compile(r"https?://(?:twitter\.com|x\.com)/\w+/status/\d+", re.IGNORECASE),
    # YouTube embeds
    "yt_embed": re.compile(
        r"https?://(?:www\.)?(?:youtube\.com/(?:watch\?v=|embed/)|youtu\.be/)[\w-]+",
        re.IGNORECASE,
    ),
    # Generic URL pattern for data attributes and JS
    "generic_url": re.compile(r'https?://[^\s"\'\)<>]+', re.IGNORECASE),
}


class ArticleExtractor(BaseExtractor):
    """Extracts content from generic web articles and pages.

    This is the fallback extractor -- it handles any URL not claimed
    by a more specific extractor. Uses trafilatura for clean text
    extraction and BeautifulSoup for structural link discovery.
    """

    @staticmethod
    def can_handle(url: str) -> bool:
        """Handles any HTTP(S) URL as a fallback."""
        return url.startswith(("http://", "https://"))

    @staticmethod
    def priority() -> int:
        return -100  # Lowest priority -- fallback extractor

    async def extract(self, url: str) -> ExtractionResult:
        import httpx

        client = await self._get_client()
        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return ExtractionResult(
                url=url,
                content_type=ContentType.ERROR,
                metadata={"error": str(e)},
            )

        html = resp.text
        content_type_header = resp.headers.get("content-type", "")

        # Handle PDFs that got routed here
        if "application/pdf" in content_type_header:
            return ExtractionResult(
                url=url,
                content_type=ContentType.PDF,
                content="[PDF detected -- use PDF extractor]",
                metadata={"content_type_header": content_type_header},
            )

        # Extract main content with trafilatura
        title, content = self._extract_content(html, url)

        # Extract all discoverable links
        links = self._extract_links(html, url)

        # Extract metadata
        metadata = self._extract_metadata(html, url)

        return ExtractionResult(
            url=url,
            title=title,
            content=content[: self.config.max_content_length],
            content_type=ContentType.ARTICLE,
            links=links,
            metadata=metadata,
            raw_html=html[:10_000],  # Keep a snippet for debugging
        )

    def _extract_content(self, html: str, url: str) -> tuple[str, str]:
        """Extract clean text content from HTML."""
        title = ""
        content = ""

        # Try trafilatura first (best quality)
        if trafilatura is not None:
            extracted = trafilatura.extract(
                html,
                url=url,
                include_links=False,
                include_comments=False,
                include_tables=True,
                favor_precision=True,
            )
            if extracted:
                content = extracted

            metadata = trafilatura.extract(
                html,
                url=url,
                output_format="json",
                include_links=False,
            )
            if metadata:
                import json

                try:
                    meta = json.loads(metadata)
                    title = meta.get("title", "")
                except (json.JSONDecodeError, TypeError):
                    pass

        # Get title from BS4 if trafilatura didn't provide one
        if not title:
            soup = BeautifulSoup(html, "lxml")
            title_tag = soup.find("title")
            if title_tag:
                title = title_tag.get_text(strip=True)

        # Fallback: BeautifulSoup content extraction
        if not content:
            soup = BeautifulSoup(html, "lxml")

            # Remove noise elements
            for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()

            # Try article tag first, then main, then body
            for selector in ["article", "main", "[role='main']", "body"]:
                article = soup.select_one(selector)
                if article:
                    content = article.get_text(separator="\n", strip=True)
                    break

        return title, content

    def _extract_links(self, html: str, base_url: str) -> list[str]:
        """Extract all interesting links from the page.

        This goes beyond simple <a href> tags -- it also finds:
        - Embedded tweet URLs (in blockquotes, data attributes, iframes)
        - YouTube embeds (iframes, data attributes)
        - Links in structured data / JSON-LD
        - URLs in data-* attributes
        """
        soup = BeautifulSoup(html, "lxml")
        found_urls: set[str] = set()

        # 1. Standard <a> tags
        for a in soup.find_all("a", href=True):
            href = str(a["href"])
            if href and not href.startswith(("#", "javascript:", "mailto:")):
                absolute = urljoin(base_url, href)
                found_urls.add(absolute)

        # 2. Iframes (YouTube embeds, etc.)
        for iframe in soup.find_all("iframe", src=True):
            src = str(iframe["src"])
            absolute = urljoin(base_url, src)
            found_urls.add(absolute)

        # 3. Embedded tweet blockquotes (Twitter widget format)
        for bq in soup.find_all("blockquote", class_="twitter-tweet"):
            for a in bq.find_all("a", href=True):
                href = str(a["href"])
                if "twitter.com" in href or "x.com" in href:
                    found_urls.add(href)

        # 4. data-* attributes that might contain URLs
        for tag in soup.find_all(attrs={"data-src": True}):
            found_urls.add(urljoin(base_url, str(tag["data-src"])))
        for tag in soup.find_all(attrs={"data-url": True}):
            found_urls.add(urljoin(base_url, str(tag["data-url"])))
        for tag in soup.find_all(attrs={"data-href": True}):
            found_urls.add(urljoin(base_url, str(tag["data-href"])))

        # 5. Scan raw HTML for embedded X/Twitter and YouTube URLs
        #    (catches dynamically injected embeds)
        if self.config.extract_embedded_urls:
            for pattern_name, pattern in EMBED_PATTERNS.items():
                if pattern_name == "generic_url":
                    continue  # Skip generic -- too noisy
                for match in pattern.finditer(html):
                    url = match.group(0).rstrip('",;)\\')
                    found_urls.add(url)

        # Filter and deduplicate
        filtered = self._filter_links(found_urls, base_url)
        return filtered[: self.config.max_links_per_page]

    def _filter_links(self, urls: set[str], base_url: str) -> list[str]:
        """Filter extracted URLs to keep only interesting ones."""
        base_domain = urlparse(base_url).netloc
        interesting = []

        # Domains we always want to follow
        high_value_domains = {
            "twitter.com",
            "x.com",
            "youtube.com",
            "youtu.be",
            "github.com",
            "medium.com",
            "substack.com",
        }

        for url in urls:
            parsed = urlparse(url)

            # Skip non-HTTP
            if parsed.scheme not in ("http", "https"):
                continue

            # Skip common junk
            if any(
                skip in url.lower()
                for skip in [
                    "/share?",
                    "/intent/",
                    "accounts.google",
                    "login",
                    "signup",
                    "signin",
                    "/auth/",
                    ".css",
                    ".js",
                    ".ico",
                    ".png",
                    ".jpg",
                    ".gif",
                    "privacy",
                    "terms",
                    "cookie",
                ]
            ):
                continue

            domain = parsed.netloc.lower().removeprefix("www.")

            # Always keep high-value domains
            if any(hvd in domain for hvd in high_value_domains):
                interesting.append(url)
                continue

            # If configured, only follow same-domain links
            if self.config.follow_same_domain_only:
                if domain == base_domain.lower().removeprefix("www."):
                    interesting.append(url)
                continue

            # Keep external links too (they might be interesting articles)
            interesting.append(url)

        return list(dict.fromkeys(interesting))  # Dedup preserving order

    def _extract_metadata(self, html: str, url: str) -> dict:
        """Extract page metadata (Open Graph, meta tags, etc.)."""
        soup = BeautifulSoup(html, "lxml")
        metadata: dict[str, str] = {"source_url": url}

        # Open Graph tags
        for og in soup.find_all("meta", property=re.compile(r"^og:")):
            prop = str(og.get("property", "")).replace("og:", "")
            content = str(og.get("content", ""))
            if prop and content:
                metadata[f"og_{prop}"] = content

        # Twitter card tags
        for tc in soup.find_all("meta", attrs={"name": re.compile(r"^twitter:")}):
            name = str(tc.get("name", "")).replace("twitter:", "")
            content = str(tc.get("content", ""))
            if name and content:
                metadata[f"twitter_{name}"] = content

        # Standard meta tags
        for name_key in ["author", "description", "keywords", "date", "published_time"]:
            tag = soup.find("meta", attrs={"name": name_key})
            if tag and tag.get("content"):
                metadata[name_key] = str(tag["content"])

        return metadata
