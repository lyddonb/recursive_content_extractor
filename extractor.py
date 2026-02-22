"""Recursive Content Extractor — main orchestrator.

This is the primary entry point. It recursively extracts content from a URL,
following embedded links up to a configurable depth, building a tree of
ContentNode objects.

Usage:
    from extractor import RecursiveExtractor

    extractor = RecursiveExtractor(depth=2)
    result = await extractor.extract("https://example.com/article")
    print(result.to_markdown())
"""

from __future__ import annotations

import asyncio
import fnmatch
import logging
from typing import Type
from urllib.parse import urlparse

from classifier import URLClassifier
from extractors import BaseExtractor
from models import ContentNode, ContentType, ExtractorConfig

logger = logging.getLogger(__name__)


class RecursiveExtractor:
    """Recursively extracts content from URLs, following links to build a context tree.

    Args:
        depth: Maximum recursion depth (0 = root only, 1 = root + direct links, etc.)
        config: Full configuration object (overrides depth if provided)

    Example:
        extractor = RecursiveExtractor(depth=1)
        result = await extractor.extract("https://example.com")
        print(result.to_json())
    """

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
        self._semaphore = asyncio.Semaphore(5)  # Max concurrent requests

    def register_extractor(
        self, extractor_class: Type[BaseExtractor], priority: int | None = None
    ):
        """Register a custom extractor.

        Args:
            extractor_class: Must implement BaseExtractor interface.
            priority: Higher values are checked first. Default from class.
        """
        self.classifier.register(extractor_class, priority)

    async def extract(self, url: str) -> ContentNode:
        """Recursively extract content starting from the given URL.

        Returns:
            ContentNode tree with all extracted content and children.
        """
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
            await self.classifier.close()

    async def _extract_recursive(self, url: str, depth: int) -> ContentNode:
        """Internal recursive extraction method."""
        # Normalize URL
        url = self._normalize_url(url)

        # Check if already visited (cycle detection)
        if url in self._visited:
            logger.debug(f"[depth={depth}] Skipping already visited: {url}")
            return ContentNode(
                url=url,
                content="[Already visited — skipping to prevent cycles]",
                content_type=ContentType.GENERIC,
                depth=depth,
            )

        self._visited.add(url)

        # Check URL against include/exclude patterns
        if not self._should_follow(url):
            logger.debug(f"[depth={depth}] URL excluded by pattern: {url}")
            return ContentNode(
                url=url,
                content="[Excluded by URL pattern filter]",
                content_type=ContentType.GENERIC,
                depth=depth,
            )

        # Extract content from this URL
        extractor_name = self.classifier.classify(url)
        logger.info(
            f"[depth={depth}] Extracting: {url} (using {extractor_name})"
        )

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

        # Build the node
        node = ContentNode(
            url=url,
            title=result.title,
            content=result.content,
            content_type=result.content_type,
            metadata=result.metadata,
            depth=depth,
        )

        # Recurse into discovered links if we haven't hit max depth
        if depth < self.config.depth and result.links:
            links_to_follow = [
                link for link in result.links
                if self._normalize_url(link) not in self._visited
                   and self._should_follow(link)
            ]

            if links_to_follow:
                logger.info(
                    f"[depth={depth}] Following {len(links_to_follow)} links "
                    f"from {url}"
                )

                # Rate limit: small delay between batches
                if self.config.rate_limit_delay > 0:
                    await asyncio.sleep(self.config.rate_limit_delay)

                # Extract children concurrently (with semaphore limiting)
                tasks = [
                    self._extract_recursive(link, depth + 1)
                    for link in links_to_follow
                ]
                children = await asyncio.gather(*tasks, return_exceptions=True)

                for child in children:
                    if isinstance(child, Exception):
                        logger.error(f"Child extraction failed: {child}")
                    elif isinstance(child, ContentNode):
                        node.children.append(child)

        return node

    def _normalize_url(self, url: str) -> str:
        """Normalize a URL to prevent duplicate visits.

        Strips fragments, trailing slashes, and normalizes scheme.
        """
        parsed = urlparse(url)

        # Remove fragment
        normalized = parsed._replace(fragment="")

        # Rebuild
        result = normalized.geturl()

        # Strip trailing slash (but not for root paths)
        if result.endswith("/") and parsed.path != "/":
            result = result.rstrip("/")

        return result

    def _should_follow(self, url: str) -> bool:
        """Check if a URL matches include/exclude patterns."""
        # Check excludes first
        for pattern in self.config.exclude_patterns:
            if fnmatch.fnmatch(url, pattern):
                return False

        # Then check includes
        if self.config.include_patterns == ["*"]:
            return True

        for pattern in self.config.include_patterns:
            if fnmatch.fnmatch(url, pattern):
                return True

        return False


# Convenience function for simple usage
async def extract_url(
    url: str,
    depth: int = 1,
    use_browser: bool = False,
) -> ContentNode:
    """Quick extraction function.

    Args:
        url: The URL to extract content from.
        depth: How many levels of links to follow (0=root only).
        use_browser: Whether to use Playwright for JS-rendered pages.

    Returns:
        ContentNode tree with all extracted content.
    """
    config = ExtractorConfig(depth=depth, use_browser=use_browser)
    extractor = RecursiveExtractor(config=config)
    return await extractor.extract(url)
