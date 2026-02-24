"""Tests for the arXiv extractor."""

from __future__ import annotations

import pytest

from recursive_content_extractor.extractors.arxiv import ArXivExtractor
from recursive_content_extractor.models import ContentType, ExtractorConfig


class TestArXivCanHandle:
    def test_handles_abs_url(self):
        assert ArXivExtractor.can_handle("https://arxiv.org/abs/2301.07041") is True

    def test_handles_old_format(self):
        assert ArXivExtractor.can_handle("https://arxiv.org/abs/hep-th/9901001") is True

    def test_handles_versioned(self):
        assert ArXivExtractor.can_handle("https://arxiv.org/abs/2301.07041v2") is True

    def test_handles_www_prefix(self):
        assert ArXivExtractor.can_handle("https://www.arxiv.org/abs/2301.07041") is True

    def test_rejects_pdf_url(self):
        assert ArXivExtractor.can_handle("https://arxiv.org/pdf/2301.07041") is False

    def test_rejects_non_arxiv(self):
        assert ArXivExtractor.can_handle("https://example.com/abs/2301.07041") is False

    def test_rejects_list_pages(self):
        assert ArXivExtractor.can_handle("https://arxiv.org/list/cs.AI/recent") is False

    def test_priority(self):
        assert ArXivExtractor.priority() == 45


class TestArXivExtract:
    @pytest.mark.asyncio
    async def test_api_success(self, httpx_mock, arxiv_atom_response):
        httpx_mock.add_response(
            url="http://export.arxiv.org/api/query?id_list=2301.07041",
            text=arxiv_atom_response,
        )

        extractor = ArXivExtractor(config=ExtractorConfig(timeout=10))
        result = await extractor.extract("https://arxiv.org/abs/2301.07041")

        assert result.content_type == ContentType.ARXIV
        assert "A Test Paper on Machine Learning" in result.title
        assert "Alice Author" in result.content
        assert "Bob Researcher" in result.content
        assert "cs.AI" in result.content
        assert "novel approach" in result.content
        assert result.metadata["source"] == "arxiv_api"
        assert result.metadata["paper_id"] == "2301.07041"
        assert len(result.metadata["authors"]) == 2
        await extractor.close()

    @pytest.mark.asyncio
    async def test_pdf_link_in_results(self, httpx_mock, arxiv_atom_response):
        httpx_mock.add_response(
            url="http://export.arxiv.org/api/query?id_list=2301.07041",
            text=arxiv_atom_response,
        )

        extractor = ArXivExtractor(config=ExtractorConfig(timeout=10))
        result = await extractor.extract("https://arxiv.org/abs/2301.07041")

        assert any("pdf" in link for link in result.links)
        await extractor.close()

    @pytest.mark.asyncio
    async def test_doi_link_in_results(self, httpx_mock, arxiv_atom_response):
        httpx_mock.add_response(
            url="http://export.arxiv.org/api/query?id_list=2301.07041",
            text=arxiv_atom_response,
        )

        extractor = ArXivExtractor(config=ExtractorConfig(timeout=10))
        result = await extractor.extract("https://arxiv.org/abs/2301.07041")

        assert "https://doi.org/10.1234/example" in result.links
        assert result.metadata["doi"] == "10.1234/example"
        await extractor.close()

    @pytest.mark.asyncio
    async def test_api_error_falls_back_to_html(self, httpx_mock):
        # API fails
        httpx_mock.add_response(
            url="http://export.arxiv.org/api/query?id_list=2301.07041",
            status_code=500,
        )
        # HTML succeeds
        httpx_mock.add_response(
            url="https://arxiv.org/abs/2301.07041",
            text="""<!DOCTYPE html>
<html>
<body>
  <h1 class="title"><span class="descriptor">Title:</span>A Fallback Paper Title</h1>
  <div class="authors"><span class="descriptor">Authors:</span>Charlie Coder</div>
  <blockquote class="abstract">
    <span class="descriptor">Abstract:</span>This is the abstract from HTML.
  </blockquote>
</body>
</html>""",
        )

        extractor = ArXivExtractor(config=ExtractorConfig(timeout=10, max_retries=0))
        result = await extractor.extract("https://arxiv.org/abs/2301.07041")

        assert result.content_type == ContentType.ARXIV
        assert "A Fallback Paper Title" in result.content
        assert "Charlie Coder" in result.content
        assert "abstract from HTML" in result.content
        assert result.metadata["source"] == "html_scraping"
        await extractor.close()

    @pytest.mark.asyncio
    async def test_all_strategies_fail(self, httpx_mock):
        httpx_mock.add_response(
            url="http://export.arxiv.org/api/query?id_list=2301.07041",
            status_code=500,
        )
        httpx_mock.add_response(
            url="https://arxiv.org/abs/2301.07041",
            status_code=500,
        )

        extractor = ArXivExtractor(config=ExtractorConfig(timeout=10, max_retries=0))
        result = await extractor.extract("https://arxiv.org/abs/2301.07041")

        assert "Could not extract" in result.content
        assert result.content_type == ContentType.ARXIV
        await extractor.close()

    @pytest.mark.asyncio
    async def test_paper_id_extraction(self):
        assert ArXivExtractor._extract_paper_id("https://arxiv.org/abs/2301.07041") == "2301.07041"
        assert (
            ArXivExtractor._extract_paper_id("https://arxiv.org/abs/2301.07041v2")
            == "2301.07041v2"
        )
        assert (
            ArXivExtractor._extract_paper_id("https://arxiv.org/abs/hep-th/9901001")
            == "hep-th/9901001"
        )
        assert ArXivExtractor._extract_paper_id("https://arxiv.org/pdf/2301.07041") is None
