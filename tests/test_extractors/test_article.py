"""Tests for the article extractor."""

from __future__ import annotations

import pytest

from recursive_content_extractor.extractors.article import ArticleExtractor
from recursive_content_extractor.models import ContentType, ExtractorConfig


class TestArticleCanHandle:
    def test_handles_http(self):
        assert ArticleExtractor.can_handle("http://example.com") is True

    def test_handles_https(self):
        assert ArticleExtractor.can_handle("https://example.com") is True

    def test_rejects_non_http(self):
        assert ArticleExtractor.can_handle("ftp://example.com") is False
        assert ArticleExtractor.can_handle("file:///tmp/test.html") is False

    def test_priority_is_lowest(self):
        assert ArticleExtractor.priority() == -100


class TestArticleExtract:
    @pytest.mark.asyncio
    async def test_extracts_content_from_html(self, httpx_mock, sample_html):
        httpx_mock.add_response(url="https://example.com/article", text=sample_html)
        extractor = ArticleExtractor(config=ExtractorConfig(timeout=10))
        result = await extractor.extract("https://example.com/article")

        assert result.content_type == ContentType.ARTICLE
        assert result.url == "https://example.com/article"
        # Should have extracted some content
        assert len(result.content) > 0
        await extractor.close()

    @pytest.mark.asyncio
    async def test_extracts_title_from_title_tag(self, httpx_mock):
        html = """<!DOCTYPE html>
<html><head><title>My Page Title</title></head>
<body><p>Short content that trafilatura will skip.</p></body>
</html>"""
        httpx_mock.add_response(url="https://example.com/title-test", text=html)
        extractor = ArticleExtractor(config=ExtractorConfig(timeout=10))
        result = await extractor.extract("https://example.com/title-test")

        # When trafilatura can't extract content, BS4 fallback gets the <title>
        assert result.title == "My Page Title"
        await extractor.close()

    @pytest.mark.asyncio
    async def test_extracts_links(self, httpx_mock, sample_html):
        httpx_mock.add_response(url="https://example.com/article", text=sample_html)
        extractor = ArticleExtractor(config=ExtractorConfig(timeout=10))
        result = await extractor.extract("https://example.com/article")

        assert len(result.links) > 0
        urls = result.links
        # Should find the links from the sample HTML
        assert any("example.com/linked-page" in u for u in urls)
        await extractor.close()

    @pytest.mark.asyncio
    async def test_extracts_embedded_links(self, httpx_mock, sample_html_with_embeds):
        httpx_mock.add_response(url="https://example.com/embeds", text=sample_html_with_embeds)
        extractor = ArticleExtractor(config=ExtractorConfig(timeout=10))
        result = await extractor.extract("https://example.com/embeds")

        urls = result.links
        # Should find twitter embed
        assert any("twitter.com" in u or "x.com" in u for u in urls)
        # Should find youtube iframe
        assert any("youtube.com" in u for u in urls)
        await extractor.close()

    @pytest.mark.asyncio
    async def test_handles_http_error(self, httpx_mock):
        httpx_mock.add_response(url="https://example.com/404", status_code=404)
        extractor = ArticleExtractor(config=ExtractorConfig(timeout=10))
        result = await extractor.extract("https://example.com/404")

        assert result.content_type == ContentType.ERROR
        await extractor.close()

    @pytest.mark.asyncio
    async def test_detects_pdf_content_type(self, httpx_mock):
        httpx_mock.add_response(
            url="https://example.com/doc",
            text="not a real pdf",
            headers={"content-type": "application/pdf"},
        )
        extractor = ArticleExtractor(config=ExtractorConfig(timeout=10))
        result = await extractor.extract("https://example.com/doc")

        assert result.content_type == ContentType.PDF
        await extractor.close()

    @pytest.mark.asyncio
    async def test_respects_max_content_length(self, httpx_mock):
        long_content = "<html><body><article>" + "x" * 10_000 + "</article></body></html>"
        httpx_mock.add_response(url="https://example.com/long", text=long_content)
        extractor = ArticleExtractor(config=ExtractorConfig(timeout=10, max_content_length=100))
        result = await extractor.extract("https://example.com/long")

        assert len(result.content) <= 100
        await extractor.close()
