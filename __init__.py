"""Base extractor interface."""

from __future__ import annotations

import abc
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models import ExtractionResult, ExtractorConfig

logger = logging.getLogger(__name__)


class BaseExtractor(abc.ABC):
    """Abstract base class for all content extractors.

    To create a custom extractor:
    1. Subclass BaseExtractor
    2. Implement can_handle() to match your URL patterns
    3. Implement extract() to return an ExtractionResult
    4. Register with RecursiveExtractor.register_extractor()
    """

    def __init__(self, config: ExtractorConfig | None = None):
        from models import ExtractorConfig
        self.config = config or ExtractorConfig()

    @staticmethod
    @abc.abstractmethod
    def can_handle(url: str) -> bool:
        """Return True if this extractor can handle the given URL."""
        ...

    @abc.abstractmethod
    async def extract(self, url: str) -> ExtractionResult:
        """Extract content from the given URL.

        Returns:
            ExtractionResult with content, title, extracted links, and metadata.
        """
        ...

    @staticmethod
    def priority() -> int:
        """Higher priority extractors are checked first. Default: 0."""
        return 0
