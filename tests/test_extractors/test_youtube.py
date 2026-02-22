"""Tests for the YouTube extractor."""

from __future__ import annotations

import pytest

from recursive_content_extractor.extractors.youtube import (
    YouTubeExtractor,
    extract_video_id,
)
from recursive_content_extractor.models import ContentType, ExtractorConfig


class TestExtractVideoId:
    def test_standard_watch_url(self):
        assert extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_short_url(self):
        assert extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_embed_url(self):
        assert extract_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_shorts_url(self):
        assert extract_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_v_url(self):
        assert extract_video_id("https://www.youtube.com/v/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_with_extra_params(self):
        assert (
            extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=60") == "dQw4w9WgXcQ"
        )

    def test_no_video_id(self):
        assert extract_video_id("https://www.youtube.com/") is None
        assert extract_video_id("https://example.com") is None


class TestYouTubeCanHandle:
    def test_handles_youtube_com(self):
        assert YouTubeExtractor.can_handle("https://www.youtube.com/watch?v=abc") is True

    def test_handles_youtu_be(self):
        assert YouTubeExtractor.can_handle("https://youtu.be/abc") is True

    def test_handles_mobile_youtube(self):
        assert YouTubeExtractor.can_handle("https://m.youtube.com/watch?v=abc") is True

    def test_rejects_non_youtube(self):
        assert YouTubeExtractor.can_handle("https://example.com") is False
        assert YouTubeExtractor.can_handle("https://notyoutube.com/watch") is False

    def test_priority(self):
        assert YouTubeExtractor.priority() == 50


class TestYouTubeExtract:
    @pytest.mark.asyncio
    async def test_extracts_with_oembed(self, httpx_mock, oembed_response):
        httpx_mock.add_response(
            url="https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ&format=json",
            json=oembed_response,
        )
        extractor = YouTubeExtractor(config=ExtractorConfig(timeout=10))
        result = await extractor.extract("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

        assert result.content_type == ContentType.YOUTUBE
        assert result.title == "Test Video Title"
        assert "Test Channel" in result.content
        assert result.metadata["video_id"] == "dQw4w9WgXcQ"
        await extractor.close()

    @pytest.mark.asyncio
    async def test_no_video_id(self, httpx_mock):
        extractor = YouTubeExtractor(config=ExtractorConfig(timeout=10))
        result = await extractor.extract("https://www.youtube.com/")

        assert "Could not extract video ID" in result.content
        await extractor.close()

    @pytest.mark.asyncio
    async def test_canonical_url_in_result(self, httpx_mock, oembed_response):
        httpx_mock.add_response(
            url="https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ&format=json",
            json=oembed_response,
        )
        extractor = YouTubeExtractor(config=ExtractorConfig(timeout=10))
        result = await extractor.extract("https://youtu.be/dQw4w9WgXcQ")

        assert result.url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        await extractor.close()
