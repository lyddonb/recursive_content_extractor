"""Recursive Content Extractor -- main orchestrator.

This is the primary entry point. It recursively extracts content from a URL,
following embedded links up to a configurable depth, building a tree of
ContentNode objects.

Usage:
    async with RecursiveExtractor(depth=2) as extractor:
        result = await extractor.extract("https://example.com/article")
        print(result.to_markdown())
"""

from __future__ import annotations

import asyncio
import fnmatch
import logging
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlencode, urlparse

from recursive_content_extractor.classifier import URLClassifier
from recursive_content_extractor.models import ContentNode, ContentType, ExtractorConfig

if TYPE_CHECKING:
    from recursive_content_extractor.extractors.base import BaseExtractor

logger = logging.getLogger(__name__)


class RecursiveExtractor:
    """Recursively extracts content from URLs, following links to build a context tree."""

    def __init__(
        self,
        depth: int = 1,
        config: ExtractorConfig | None = None,
    ):
        if config:
            self.config = config
        else:
            self.config = ExtractorConfig(depth=depth)

        self.classifier = URLClassifier(config=self.config)
        self._visited: set[str] = set()
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)

    def register_extractor(
        self, extractor_class: type[BaseExtractor], priority: int | None = None
    ):
        """Register a custom extractor."""
        self.classifier.register(extractor_class, priority)

    async def __aenter__(self) -> RecursiveExtractor:
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: object
    ) -> None:
        await self.close()

    async def close(self) -> None:
        """Close all extractor resources (HTTP clients, browser)."""
        await self.classifier.close()

    async def extract(self, url: str) -> ContentNode:
        """Recursively extract content starting from the given URL."""
        self._visited.clear()
        logger.info(f"Starting extraction: {url} (max depth: {self.config.depth})")

        try:
            root = await self._extract_recursive(url, depth=0)
            logger.info(
                f"Extraction complete: {root.total_nodes} nodes, "
                f"{root.total_content_length:,} chars total"
            )
            return root
        finally:
            await self.close()

    async def _extract_recursive(self, url: str, depth: int) -> ContentNode:
        """Internal recursive extraction method."""
        url = self._normalize_url(url)

        if url in self._visited:
            logger.debug(f"[depth={depth}] Skipping already visited: {url}")
            return ContentNode(
                url=url,
                content="[Already visited -- skipping to prevent cycles]",
                content_type=ContentType.GENERIC,
                depth=depth,
            )

        self._visited.add(url)

        if not self._should_follow(url):
            logger.debug(f"[depth={depth}] URL excluded by pattern: {url}")
            return ContentNode(
                url=url,
                content="[Excluded by URL pattern filter]",
                content_type=ContentType.GENERIC,
                depth=depth,
            )

        extractor_name = self.classifier.classify(url)
        logger.info(f"[depth={depth}] Extracting: {url} (using {extractor_name})")

        async with self._semaphore:
            extractor = self.classifier.get_extractor(url)
            try:
                result = await extractor.extract(url)
            except Exception as e:
                logger.error(f"[depth={depth}] Extraction failed for {url}: {e}")
                return ContentNode(
                    url=url,
                    content_type=ContentType.ERROR,
                    error=str(e),
                    depth=depth,
                )

        node = ContentNode(
            url=url,
            title=result.title,
            content=result.content,
            content_type=result.content_type,
            metadata=result.metadata,
            depth=depth,
        )

        if depth < self.config.depth and result.links:
            links_to_follow = [
                link
                for link in result.links
                if self._normalize_url(link) not in self._visited and self._should_follow(link)
            ]

            if links_to_follow:
                logger.info(f"[depth={depth}] Following {len(links_to_follow)} links from {url}")

                if self.config.rate_limit_delay > 0:
                    await asyncio.sleep(self.config.rate_limit_delay)

                tasks = [self._extract_recursive(link, depth + 1) for link in links_to_follow]
                children = await asyncio.gather(*tasks, return_exceptions=True)

                for child in children:
                    if isinstance(child, Exception):
                        logger.error(f"Child extraction failed: {child}")
                    elif isinstance(child, ContentNode):
                        node.children.append(child)

        return node

    def _normalize_url(self, url: str) -> str:
        """Normalize a URL to prevent duplicate visits.

        Strips fragments, trailing slashes, normalizes scheme/domain/query params.
        """
        parsed = urlparse(url)

        # Normalize scheme: http -> https
        scheme = "https" if parsed.scheme in ("http", "https") else parsed.scheme

        # Lowercase and strip www from domain
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]

        # Remove fragment
        # Sort query parameters for consistent dedup
        query = urlencode(
            sorted(parse_qs(parsed.query, keep_blank_values=True).items()), doseq=True
        )

        normalized = parsed._replace(scheme=scheme, netloc=netloc, fragment="", query=query)
        result = normalized.geturl()

        # Strip trailing slash (but not for root paths)
        if result.endswith("/") and parsed.path not in ("/", ""):
            result = result.rstrip("/")

        return result

    def _should_follow(self, url: str) -> bool:
        """Check if a URL matches include/exclude patterns."""
        for pattern in self.config.exclude_patterns:
            if fnmatch.fnmatch(url, pattern):
                return False

        if self.config.include_patterns == ["*"]:
            return True

        return any(fnmatch.fnmatch(url, pattern) for pattern in self.config.include_patterns)


async def extract_url(
    url: str,
    depth: int = 1,
    use_browser: bool = False,
) -> ContentNode:
    """Quick extraction function."""
    config = ExtractorConfig(depth=depth, use_browser=use_browser)
    async with RecursiveExtractor(config=config) as extractor:
        return await extractor.extract(url)
