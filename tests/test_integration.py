"""Integration tests that make real network calls.

All tests are marked with @pytest.mark.network and skipped by default.
Run with: uv run pytest -m network -v
"""

from __future__ import annotations

import pytest

from recursive_content_extractor.extractor import RecursiveExtractor
from recursive_content_extractor.models import ContentNode, ContentType, ExtractorConfig

pytestmark = pytest.mark.network


@pytest.fixture()
def config() -> ExtractorConfig:
    """Shared config with a reasonable timeout for live requests."""
    return ExtractorConfig(depth=0, timeout=15, rate_limit_delay=0)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_extract_article(config: ExtractorConfig):
    """Smoke-test the full pipeline against a simple HTML page."""
    ext = RecursiveExtractor(config=config)
    node = await ext.extract("https://httpbin.org/html")

    assert isinstance(node, ContentNode)
    assert node.content_type == ContentType.ARTICLE
    assert node.content
    assert node.error is None


async def test_extract_youtube_video(config: ExtractorConfig):
    """Extract a well-known YouTube video (Rick Astley - Never Gonna Give You Up)."""
    ext = RecursiveExtractor(config=config)
    node = await ext.extract("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    assert isinstance(node, ContentNode)
    assert node.content_type == ContentType.YOUTUBE
    assert node.title
    assert node.content


async def test_extract_arxiv_paper(config: ExtractorConfig):
    """Extract the 'Attention Is All You Need' arXiv paper."""
    ext = RecursiveExtractor(config=config)
    node = await ext.extract("https://arxiv.org/abs/1706.03762")

    assert isinstance(node, ContentNode)
    assert node.content_type == ContentType.ARXIV
    assert node.title
    assert node.content


async def test_extract_github_repo(config: ExtractorConfig):
    """Extract a stable GitHub repo (psf/requests)."""
    ext = RecursiveExtractor(config=config)
    node = await ext.extract("https://github.com/psf/requests")

    assert isinstance(node, ContentNode)
    assert node.content_type == ContentType.GITHUB
    assert node.title
    assert node.content


async def test_recursive_depth(config: ExtractorConfig):
    """Verify the pipeline completes at depth=1 without errors."""
    deep_config = ExtractorConfig(depth=1, timeout=15, rate_limit_delay=0)
    ext = RecursiveExtractor(config=deep_config)
    node = await ext.extract("https://httpbin.org/html")

    assert isinstance(node, ContentNode)
    assert node.error is None
    # children may be empty for httpbin's simple page, but the list must exist
    assert isinstance(node.children, list)
