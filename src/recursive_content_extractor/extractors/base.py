"""Base extractor interface."""

from __future__ import annotations

import abc
import logging
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from recursive_content_extractor.models import ExtractionResult, ExtractorConfig

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
        from recursive_content_extractor.models import ExtractorConfig

        self.config = config or ExtractorConfig()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create a shared HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.config.timeout,
                headers={"User-Agent": self.config.user_agent},
                follow_redirects=True,
            )
        return self._client

    @staticmethod
    @abc.abstractmethod
    def can_handle(url: str) -> bool:
        """Return True if this extractor can handle the given URL."""
        ...

    @abc.abstractmethod
    async def extract(self, url: str) -> ExtractionResult:
        """Extract content from the given URL."""
        ...

    @staticmethod
    def priority() -> int:
        """Higher priority extractors are checked first. Default: 0."""
        return 0

    async def close(self):
        """Close the shared HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
