"""Tests for the RecursiveExtractor orchestrator."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from recursive_content_extractor.extractor import RecursiveExtractor
from recursive_content_extractor.extractors.base import BaseExtractor
from recursive_content_extractor.models import (
    ContentType,
    ExtractionResult,
    ExtractorConfig,
)


class MockExtractor(BaseExtractor):
    """A mock extractor that returns predefined results."""

    def __init__(self, config=None, results=None):
        super().__init__(config)
        self._results = results or {}

    @staticmethod
    def can_handle(url: str) -> bool:
        return url.startswith(("http://", "https://"))

    async def extract(self, url: str) -> ExtractionResult:
        if url in self._results:
            return self._results[url]
        return ExtractionResult(
            url=url,
            title=f"Page: {url}",
            content=f"Content of {url}",
            content_type=ContentType.ARTICLE,
            links=[],
        )

    @staticmethod
    def priority() -> int:
        return 1000  # Higher than everything


class TestRecursiveExtractor:
    @pytest.mark.asyncio
    async def test_depth_zero_returns_root_only(self):
        config = ExtractorConfig(depth=0, rate_limit_delay=0)
        extractor = RecursiveExtractor(config=config)
        mock = MockExtractor(
            config=config,
            results={
                "https://example.com": ExtractionResult(
                    url="https://example.com",
                    title="Root",
                    content="Root content",
                    content_type=ContentType.ARTICLE,
                    links=["https://example.com/child"],
                ),
            },
        )
        extractor.classifier.register(type(mock), priority=1000)
        extractor.classifier._instances[type(mock)] = mock

        result = await extractor.extract("https://example.com")
        assert result.title == "Root"
        assert result.children == []  # depth=0 means no recursion

    @pytest.mark.asyncio
    async def test_depth_one_follows_links(self):
        config = ExtractorConfig(depth=1, rate_limit_delay=0)
        extractor = RecursiveExtractor(config=config)
        mock = MockExtractor(
            config=config,
            results={
                "https://example.com": ExtractionResult(
                    url="https://example.com",
                    title="Root",
                    content="Root content",
                    content_type=ContentType.ARTICLE,
                    links=["https://example.com/child"],
                ),
                "https://example.com/child": ExtractionResult(
                    url="https://example.com/child",
                    title="Child",
                    content="Child content",
                    content_type=ContentType.ARTICLE,
                    links=[],
                ),
            },
        )
        extractor.classifier.register(type(mock), priority=1000)
        extractor.classifier._instances[type(mock)] = mock

        result = await extractor.extract("https://example.com")
        assert result.title == "Root"
        assert len(result.children) == 1
        assert result.children[0].title == "Child"

    @pytest.mark.asyncio
    async def test_cycle_detection(self):
        config = ExtractorConfig(depth=2, rate_limit_delay=0)
        extractor = RecursiveExtractor(config=config)
        mock = MockExtractor(
            config=config,
            results={
                "https://example.com": ExtractionResult(
                    url="https://example.com",
                    title="Root",
                    content="Root content",
                    content_type=ContentType.ARTICLE,
                    links=["https://example.com/page"],
                ),
                "https://example.com/page": ExtractionResult(
                    url="https://example.com/page",
                    title="Page",
                    content="Page content",
                    content_type=ContentType.ARTICLE,
                    links=["https://example.com"],  # Cycle back to root
                ),
            },
        )
        extractor.classifier.register(type(mock), priority=1000)
        extractor.classifier._instances[type(mock)] = mock

        result = await extractor.extract("https://example.com")
        # Should not infinitely recurse
        assert result.total_nodes <= 3

    @pytest.mark.asyncio
    async def test_url_filtering(self):
        config = ExtractorConfig(
            depth=1,
            rate_limit_delay=0,
            exclude_patterns=["*excluded.com*"],
        )
        extractor = RecursiveExtractor(config=config)
        mock = MockExtractor(
            config=config,
            results={
                "https://example.com": ExtractionResult(
                    url="https://example.com",
                    title="Root",
                    content="Root content",
                    content_type=ContentType.ARTICLE,
                    links=[
                        "https://example.com/good",
                        "https://excluded.com/bad",
                    ],
                ),
                "https://example.com/good": ExtractionResult(
                    url="https://example.com/good",
                    title="Good",
                    content="Good content",
                    content_type=ContentType.ARTICLE,
                    links=[],
                ),
            },
        )
        extractor.classifier.register(type(mock), priority=1000)
        extractor.classifier._instances[type(mock)] = mock

        result = await extractor.extract("https://example.com")
        child_urls = [c.url for c in result.children]
        assert any("good" in u for u in child_urls)
        # excluded.com should either not appear or be filtered
        assert not any("excluded.com" in u for u in child_urls)

    @pytest.mark.asyncio
    async def test_extraction_error_handled(self):
        config = ExtractorConfig(depth=0, rate_limit_delay=0)
        extractor = RecursiveExtractor(config=config)

        class FailingExtractor(BaseExtractor):
            @staticmethod
            def can_handle(url: str) -> bool:
                return True

            async def extract(self, url: str) -> ExtractionResult:
                raise RuntimeError("Extraction failed!")

            @staticmethod
            def priority() -> int:
                return 2000

        fail_ext = FailingExtractor(config=config)
        extractor.classifier.register(type(fail_ext), priority=2000)
        extractor.classifier._instances[type(fail_ext)] = fail_ext

        result = await extractor.extract("https://example.com")
        assert result.content_type == ContentType.ERROR
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_fetches_original_url_and_dedups_by_normalized_url(self):
        config = ExtractorConfig(depth=1, rate_limit_delay=0)
        extractor = RecursiveExtractor(config=config)
        root_url = "http://www.example.com/page?b=2&a=1"
        mock = MockExtractor(
            config=config,
            results={
                root_url: ExtractionResult(
                    url=root_url,
                    title="Root",
                    content="Root content",
                    content_type=ContentType.ARTICLE,
                    links=["https://example.com/page?a=1&b=2"],
                ),
            },
        )
        fetched: list[str] = []
        original_extract = mock.extract

        async def recording_extract(url: str) -> ExtractionResult:
            fetched.append(url)
            return await original_extract(url)

        mock.extract = recording_extract  # type: ignore[method-assign]
        extractor.classifier.register(type(mock), priority=1000)
        extractor.classifier._instances[type(mock)] = mock

        result = await extractor.extract(root_url)

        assert fetched == [root_url]
        assert result.url == root_url
        assert result.title == "Root"
        assert len(result.children) == 0

    @pytest.mark.asyncio
    async def test_extractor_error_result_sets_node_error(self):
        config = ExtractorConfig(depth=0, rate_limit_delay=0)
        extractor = RecursiveExtractor(config=config)
        mock = MockExtractor(
            config=config,
            results={
                "https://example.com": ExtractionResult(
                    url="https://example.com",
                    content_type=ContentType.ERROR,
                    metadata={"error": "connection refused"},
                ),
            },
        )
        extractor.classifier.register(type(mock), priority=1000)
        extractor.classifier._instances[type(mock)] = mock

        result = await extractor.extract("https://example.com")

        assert result.content_type == ContentType.ERROR
        assert result.error == "connection refused"

    def test_register_extractor(self):
        extractor = RecursiveExtractor(depth=0)

        class CustomExt(BaseExtractor):
            @staticmethod
            def can_handle(url: str) -> bool:
                return "custom.com" in url

            async def extract(self, url: str) -> ExtractionResult:
                return ExtractionResult(url=url)

        extractor.register_extractor(CustomExt, priority=99)
        assert extractor.classifier.classify("https://custom.com/page") == "CustomExt"

    def test_normalize_url(self):
        extractor = RecursiveExtractor(depth=0)
        # Fragment removal
        assert "#section" not in extractor._normalize_url("https://example.com/page#section")
        # Trailing slash removal
        assert not extractor._normalize_url("https://example.com/page/").endswith("/")
        # Root path keeps slash
        normalized_root = extractor._normalize_url("https://example.com/")
        assert normalized_root.endswith("/")

    def test_should_follow_default(self):
        extractor = RecursiveExtractor(depth=0)
        assert extractor._should_follow("https://example.com") is True

    def test_should_follow_with_exclude(self):
        config = ExtractorConfig(exclude_patterns=["*bad.com*"])
        extractor = RecursiveExtractor(config=config)
        assert extractor._should_follow("https://bad.com/page") is False
        assert extractor._should_follow("https://good.com/page") is True


class TestAsyncContextManager:
    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """Verify async with works and returns the correct result."""
        config = ExtractorConfig(depth=0, rate_limit_delay=0)
        async with RecursiveExtractor(config=config) as extractor:
            assert isinstance(extractor, RecursiveExtractor)
            mock = MockExtractor(
                config=config,
                results={
                    "https://example.com": ExtractionResult(
                        url="https://example.com",
                        title="Test",
                        content="Test content",
                        content_type=ContentType.ARTICLE,
                        links=[],
                    ),
                },
            )
            extractor.classifier.register(type(mock), priority=1000)
            extractor.classifier._instances[type(mock)] = mock

            result = await extractor.extract("https://example.com")
            assert result.title == "Test"

    @pytest.mark.asyncio
    async def test_close_is_idempotent(self):
        """Calling close() twice doesn't raise."""
        extractor = RecursiveExtractor(depth=0)
        await extractor.close()
        await extractor.close()  # Should not raise

    @pytest.mark.asyncio
    async def test_context_manager_calls_close(self):
        """Verify classifier.close() is called on normal exit."""
        config = ExtractorConfig(depth=0)
        extractor = RecursiveExtractor(config=config)
        extractor.classifier.close = AsyncMock()

        async with extractor:
            pass

        extractor.classifier.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_calls_close_on_exception(self):
        """Verify cleanup happens even when an exception is raised."""
        config = ExtractorConfig(depth=0)
        extractor = RecursiveExtractor(config=config)
        extractor.classifier.close = AsyncMock()

        with pytest.raises(ValueError, match="boom"):
            async with extractor:
                raise ValueError("boom")

        extractor.classifier.close.assert_called_once()
