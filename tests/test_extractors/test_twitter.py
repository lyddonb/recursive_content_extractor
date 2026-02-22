"""Tests for the Twitter extractor."""

from __future__ import annotations

import pytest

from recursive_content_extractor.extractors.twitter import TwitterExtractor
from recursive_content_extractor.models import ContentType, ExtractorConfig


class TestTwitterCanHandle:
    def test_handles_twitter_com(self):
        assert TwitterExtractor.can_handle("https://twitter.com/user/status/123") is True

    def test_handles_x_com(self):
        assert TwitterExtractor.can_handle("https://x.com/user/status/123") is True

    def test_handles_www_prefix(self):
        assert TwitterExtractor.can_handle("https://www.twitter.com/user/status/123") is True
        assert TwitterExtractor.can_handle("https://www.x.com/user/status/123") is True

    def test_rejects_non_twitter(self):
        assert TwitterExtractor.can_handle("https://example.com") is False
        assert TwitterExtractor.can_handle("https://notwitter.com/status/123") is False

    def test_priority(self):
        assert TwitterExtractor.priority() == 50


class TestTwitterExtract:
    @pytest.mark.asyncio
    async def test_fxtwitter_success(self, httpx_mock, fxtwitter_response):
        httpx_mock.add_response(
            url="https://api.fxtwitter.com/testuser/status/123",
            json=fxtwitter_response,
        )
        extractor = TwitterExtractor(config=ExtractorConfig(timeout=10))
        result = await extractor.extract("https://x.com/testuser/status/123")

        assert result.content_type == ContentType.X_POST
        assert "test tweet" in result.content
        assert result.metadata["source"] == "fxtwitter"
        assert result.metadata["username"] == "testuser"
        await extractor.close()

    @pytest.mark.asyncio
    async def test_falls_back_to_syndication(self, httpx_mock, syndication_response):
        # FxTwitter fails
        httpx_mock.add_response(
            url="https://api.fxtwitter.com/syndiuser/status/456",
            status_code=404,
        )
        # Syndication succeeds
        httpx_mock.add_response(
            url="https://cdn.syndication.twimg.com/tweet-result?id=456&token=0",
            json=syndication_response,
        )
        extractor = TwitterExtractor(config=ExtractorConfig(timeout=10))
        result = await extractor.extract("https://x.com/syndiuser/status/456")

        assert result.content_type == ContentType.X_POST
        assert "syndicated tweet" in result.content
        assert result.metadata["source"] == "syndication"
        await extractor.close()

    @pytest.mark.asyncio
    async def test_non_status_url(self, httpx_mock):
        extractor = TwitterExtractor(config=ExtractorConfig(timeout=10))
        result = await extractor.extract("https://x.com/someuser")

        assert result.content_type == ContentType.X_POST
        assert "Non-status" in result.content
        await extractor.close()

    @pytest.mark.asyncio
    async def test_all_strategies_fail(self, httpx_mock):
        httpx_mock.add_response(
            url="https://api.fxtwitter.com/user/status/789",
            status_code=500,
        )
        httpx_mock.add_response(
            url="https://cdn.syndication.twimg.com/tweet-result?id=789&token=0",
            status_code=500,
        )
        extractor = TwitterExtractor(config=ExtractorConfig(timeout=10))
        result = await extractor.extract("https://x.com/user/status/789")

        assert "Could not extract" in result.content
        await extractor.close()

    @pytest.mark.asyncio
    async def test_extracts_links_from_fxtwitter(self, httpx_mock, fxtwitter_response):
        httpx_mock.add_response(
            url="https://api.fxtwitter.com/testuser/status/123",
            json=fxtwitter_response,
        )
        extractor = TwitterExtractor(config=ExtractorConfig(timeout=10))
        result = await extractor.extract("https://x.com/testuser/status/123")

        assert "https://example.com/linked" in result.links
        await extractor.close()
