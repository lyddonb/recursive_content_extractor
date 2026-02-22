"""URL classifier -- routes URLs to the appropriate extractor.

The classifier checks each registered extractor's can_handle() method
in priority order and returns the first match.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from recursive_content_extractor.extractors.article import ArticleExtractor
from recursive_content_extractor.extractors.pdf import PDFExtractor
from recursive_content_extractor.extractors.twitter import TwitterExtractor
from recursive_content_extractor.extractors.youtube import YouTubeExtractor
from recursive_content_extractor.models import ExtractorConfig

if TYPE_CHECKING:
    from recursive_content_extractor.extractors.base import BaseExtractor

logger = logging.getLogger(__name__)


class URLClassifier:
    """Routes URLs to the appropriate extractor based on URL patterns.

    Extractors are checked in priority order (highest first).
    The ArticleExtractor serves as a catch-all fallback.
    """

    def __init__(self, config: ExtractorConfig | None = None):
        self.config = config or ExtractorConfig()
        self._extractors: list[tuple[int, type[BaseExtractor]]] = []
        self._instances: dict[type[BaseExtractor], BaseExtractor] = {}

        # Register default extractors
        self.register(TwitterExtractor)
        self.register(YouTubeExtractor)
        self.register(PDFExtractor)
        self.register(ArticleExtractor)

    def register(self, extractor_class: type[BaseExtractor], priority: int | None = None):
        """Register an extractor class."""
        prio = priority if priority is not None else extractor_class.priority()
        self._extractors.append((prio, extractor_class))
        self._extractors.sort(key=lambda x: x[0], reverse=True)
        logger.debug(f"Registered {extractor_class.__name__} with priority {prio}")

    def get_extractor(self, url: str) -> BaseExtractor:
        """Return the appropriate extractor instance for a URL."""
        for _priority, ext_class in self._extractors:
            if ext_class.can_handle(url):
                if ext_class not in self._instances:
                    self._instances[ext_class] = ext_class(config=self.config)
                return self._instances[ext_class]

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
