"""URL classifier — routes URLs to the appropriate extractor.

The classifier checks each registered extractor's can_handle() method
in priority order and returns the first match.
"""

from __future__ import annotations

import logging
from typing import Type

from extractors import BaseExtractor
from extractors.article import ArticleExtractor
from extractors.pdf import PDFExtractor
from extractors.twitter import TwitterExtractor
from extractors.youtube import YouTubeExtractor
from models import ExtractorConfig

logger = logging.getLogger(__name__)


class URLClassifier:
    """Routes URLs to the appropriate extractor based on URL patterns.

    Extractors are checked in priority order (highest first).
    The ArticleExtractor serves as a catch-all fallback.
    """

    def __init__(self, config: ExtractorConfig | None = None):
        self.config = config or ExtractorConfig()
        # List of (priority, extractor_class) tuples
        self._extractors: list[tuple[int, Type[BaseExtractor]]] = []
        # Cache of instantiated extractors
        self._instances: dict[Type[BaseExtractor], BaseExtractor] = {}

        # Register default extractors
        self.register(TwitterExtractor)
        self.register(YouTubeExtractor)
        self.register(PDFExtractor)
        self.register(ArticleExtractor)

    def register(
        self, extractor_class: Type[BaseExtractor], priority: int | None = None
    ):
        """Register an extractor class.

        Args:
            extractor_class: The extractor class to register.
            priority: Override the class's default priority.
        """
        prio = priority if priority is not None else extractor_class.priority()
        self._extractors.append((prio, extractor_class))
        # Re-sort by priority (highest first)
        self._extractors.sort(key=lambda x: x[0], reverse=True)
        logger.debug(
            f"Registered {extractor_class.__name__} with priority {prio}"
        )

    def get_extractor(self, url: str) -> BaseExtractor:
        """Return the appropriate extractor instance for a URL.

        Checks extractors in priority order, returns the first match.
        """
        for _priority, ext_class in self._extractors:
            if ext_class.can_handle(url):
                # Lazily instantiate and cache
                if ext_class not in self._instances:
                    self._instances[ext_class] = ext_class(config=self.config)
                return self._instances[ext_class]

        # Should never reach here if ArticleExtractor is registered
        raise ValueError(f"No extractor found for URL: {url}")

    def classify(self, url: str) -> str:
        """Return the name of the extractor that would handle this URL."""
        for _priority, ext_class in self._extractors:
            if ext_class.can_handle(url):
                return ext_class.__name__
        return "Unknown"

    async def close(self):
        """Close all extractor instances."""
        for instance in self._instances.values():
            if hasattr(instance, "close"):
                await instance.close()
