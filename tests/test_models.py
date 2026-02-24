"""Tests for data models."""

from __future__ import annotations

import json

import pytest

from recursive_content_extractor.models import (
    ContentNode,
    ContentType,
    ExtractionResult,
    ExtractorConfig,
)


class TestContentType:
    def test_enum_values(self):
        assert ContentType.ARTICLE == "article"
        assert ContentType.X_THREAD == "x_thread"
        assert ContentType.YOUTUBE == "youtube"
        assert ContentType.PDF == "pdf"
        assert ContentType.ERROR == "error"

    def test_string_comparison(self):
        assert ContentType.ARTICLE == "article"
        assert ContentType("youtube") == ContentType.YOUTUBE


class TestExtractionResult:
    def test_default_values(self):
        result = ExtractionResult(url="https://example.com")
        assert result.url == "https://example.com"
        assert result.title == ""
        assert result.content == ""
        assert result.content_type == ContentType.UNKNOWN
        assert result.links == []
        assert result.metadata == {}
        assert result.extracted_at  # Should be set automatically

    def test_extracted_at_uses_utc(self):
        result = ExtractionResult(url="https://example.com")
        # Should contain timezone info (UTC offset)
        assert "+" in result.extracted_at or "Z" in result.extracted_at

    def test_repr(self):
        result = ExtractionResult(
            url="https://example.com",
            content="hello",
            content_type=ContentType.ARTICLE,
            links=["a", "b"],
        )
        r = repr(result)
        assert "example.com" in r
        assert "article" in r
        assert "content_len=5" in r
        assert "links=2" in r


class TestContentNode:
    def test_default_values(self):
        node = ContentNode(url="https://example.com")
        assert node.url == "https://example.com"
        assert node.children == []
        assert node.depth == 0
        assert node.error is None

    def test_to_dict(self):
        node = ContentNode(
            url="https://example.com",
            title="Test",
            content="Content",
            content_type=ContentType.ARTICLE,
        )
        d = node.to_dict()
        assert d["url"] == "https://example.com"
        assert d["title"] == "Test"
        assert d["content_type"] == "article"
        assert d["children"] == []

    def test_to_json(self):
        node = ContentNode(url="https://example.com", title="Test")
        j = node.to_json()
        parsed = json.loads(j)
        assert parsed["url"] == "https://example.com"
        assert parsed["title"] == "Test"

    def test_to_markdown(self):
        node = ContentNode(
            url="https://example.com",
            title="Test Article",
            content="Some content",
            content_type=ContentType.ARTICLE,
        )
        md = node.to_markdown()
        assert "# Test Article" in md
        assert "**Source:** https://example.com" in md
        assert "**Type:** article" in md
        assert "Some content" in md

    def test_to_markdown_with_children(self):
        child = ContentNode(url="https://child.com", title="Child", content="Child content")
        parent = ContentNode(
            url="https://parent.com",
            title="Parent",
            content="Parent content",
            children=[child],
        )
        md = parent.to_markdown()
        assert "Linked Content" in md
        assert "Child" in md

    def test_flatten(self):
        grandchild = ContentNode(url="https://gc.com")
        child = ContentNode(url="https://child.com", children=[grandchild])
        root = ContentNode(url="https://root.com", children=[child])

        flat = root.flatten()
        assert len(flat) == 3
        assert flat[0].url == "https://root.com"
        assert flat[1].url == "https://child.com"
        assert flat[2].url == "https://gc.com"

    def test_total_nodes(self):
        child = ContentNode(url="https://child.com")
        root = ContentNode(url="https://root.com", children=[child])
        assert root.total_nodes == 2

    def test_total_content_length(self):
        child = ContentNode(url="https://child.com", content="12345")
        root = ContentNode(url="https://root.com", content="abc", children=[child])
        assert root.total_content_length == 8


class TestExtractorConfig:
    def test_defaults(self):
        config = ExtractorConfig()
        assert config.depth == 1
        assert config.timeout == 30
        assert config.max_links_per_page == 20
        assert config.max_concurrent_requests == 5
        assert config.rate_limit_delay == 1.0

    def test_custom_values(self):
        config = ExtractorConfig(depth=3, timeout=60, max_concurrent_requests=10)
        assert config.depth == 3
        assert config.timeout == 60
        assert config.max_concurrent_requests == 10

    def test_negative_depth_raises(self):
        with pytest.raises(ValueError, match="depth"):
            ExtractorConfig(depth=-1)

    def test_zero_timeout_raises(self):
        with pytest.raises(ValueError, match="timeout"):
            ExtractorConfig(timeout=0)

    def test_negative_timeout_raises(self):
        with pytest.raises(ValueError, match="timeout"):
            ExtractorConfig(timeout=-5)

    def test_negative_max_links_raises(self):
        with pytest.raises(ValueError, match="max_links_per_page"):
            ExtractorConfig(max_links_per_page=-1)

    def test_zero_concurrency_raises(self):
        with pytest.raises(ValueError, match="max_concurrent_requests"):
            ExtractorConfig(max_concurrent_requests=0)

    def test_negative_rate_limit_raises(self):
        with pytest.raises(ValueError, match="rate_limit_delay"):
            ExtractorConfig(rate_limit_delay=-0.5)

    def test_zero_depth_allowed(self):
        config = ExtractorConfig(depth=0)
        assert config.depth == 0

    def test_zero_rate_limit_allowed(self):
        config = ExtractorConfig(rate_limit_delay=0)
        assert config.rate_limit_delay == 0

    def test_retry_defaults(self):
        config = ExtractorConfig()
        assert config.max_retries == 2
        assert config.retry_backoff_factor == 0.5

    def test_negative_max_retries_raises(self):
        with pytest.raises(ValueError, match="max_retries"):
            ExtractorConfig(max_retries=-1)

    def test_negative_retry_backoff_raises(self):
        with pytest.raises(ValueError, match="retry_backoff_factor"):
            ExtractorConfig(retry_backoff_factor=-0.1)

    def test_zero_retries_allowed(self):
        config = ExtractorConfig(max_retries=0)
        assert config.max_retries == 0

    def test_zero_retry_backoff_allowed(self):
        config = ExtractorConfig(retry_backoff_factor=0)
        assert config.retry_backoff_factor == 0
