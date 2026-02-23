"""Tests for URL classifier."""

from __future__ import annotations

import pytest

from recursive_content_extractor.classifier import URLClassifier
from recursive_content_extractor.extractors.article import ArticleExtractor
from recursive_content_extractor.extractors.base import BaseExtractor
from recursive_content_extractor.models import ExtractionResult, ExtractorConfig


class TestURLClassifier:
    def test_routes_twitter_urls(self):
        classifier = URLClassifier()
        assert classifier.classify("https://twitter.com/user/status/123") == "TwitterExtractor"
        assert classifier.classify("https://x.com/user/status/456") == "TwitterExtractor"

    def test_routes_youtube_urls(self):
        classifier = URLClassifier()
        assert classifier.classify("https://www.youtube.com/watch?v=abc123") == "YouTubeExtractor"
        assert classifier.classify("https://youtu.be/abc123") == "YouTubeExtractor"

    def test_routes_pdf_urls(self):
        classifier = URLClassifier()
        assert classifier.classify("https://example.com/paper.pdf") == "PDFExtractor"
        assert classifier.classify("https://arxiv.org/pdf/1234.5678") == "PDFExtractor"

    def test_routes_github_urls(self):
        classifier = URLClassifier()
        assert classifier.classify("https://github.com/owner/repo") == "GitHubExtractor"
        assert (
            classifier.classify("https://github.com/owner/repo/blob/main/README.md")
            == "GitHubExtractor"
        )

    def test_routes_arxiv_abs_urls(self):
        classifier = URLClassifier()
        assert classifier.classify("https://arxiv.org/abs/2301.07041") == "ArXivExtractor"

    def test_routes_arxiv_pdf_to_pdf_extractor(self):
        classifier = URLClassifier()
        assert classifier.classify("https://arxiv.org/pdf/2301.07041") == "PDFExtractor"

    def test_routes_generic_to_article(self):
        classifier = URLClassifier()
        assert classifier.classify("https://example.com/some-article") == "ArticleExtractor"
        assert classifier.classify("https://blog.example.com/post") == "ArticleExtractor"

    def test_priority_ordering(self):
        classifier = URLClassifier()
        # Twitter and YouTube are priority 50, PDF is 40, Article is -100
        # Twitter/YouTube should be checked before article
        assert classifier.classify("https://twitter.com/user/status/123") == "TwitterExtractor"

    def test_get_extractor_returns_instance(self):
        classifier = URLClassifier()
        ext = classifier.get_extractor("https://example.com")
        assert isinstance(ext, ArticleExtractor)

    def test_get_extractor_caches_instances(self):
        classifier = URLClassifier()
        ext1 = classifier.get_extractor("https://example.com/a")
        ext2 = classifier.get_extractor("https://example.com/b")
        assert ext1 is ext2  # Same instance

    def test_get_extractor_different_types(self):
        classifier = URLClassifier()
        article = classifier.get_extractor("https://example.com")
        twitter = classifier.get_extractor("https://x.com/user/status/123")
        assert type(article) is not type(twitter)

    def test_register_custom_extractor(self):
        class CustomExtractor(BaseExtractor):
            @staticmethod
            def can_handle(url: str) -> bool:
                return "custom.example.com" in url

            async def extract(self, url: str) -> ExtractionResult:
                return ExtractionResult(url=url)

            @staticmethod
            def priority() -> int:
                return 100

        classifier = URLClassifier()
        classifier.register(CustomExtractor)
        assert classifier.classify("https://custom.example.com/page") == "CustomExtractor"

    def test_register_custom_with_override_priority(self):
        class LowPrioExtractor(BaseExtractor):
            @staticmethod
            def can_handle(url: str) -> bool:
                return True  # Matches everything

            async def extract(self, url: str) -> ExtractionResult:
                return ExtractionResult(url=url)

            @staticmethod
            def priority() -> int:
                return -200  # Lower than article

        classifier = URLClassifier()
        classifier.register(LowPrioExtractor, priority=200)  # Override to highest
        # Now it should match everything first
        assert classifier.classify("https://example.com") == "LowPrioExtractor"

    def test_no_extractor_raises(self):
        classifier = URLClassifier()
        with pytest.raises(ValueError, match="No extractor found"):
            classifier.get_extractor("ftp://not-http.example.com")

    def test_config_passed_to_extractors(self):
        config = ExtractorConfig(timeout=99)
        classifier = URLClassifier(config=config)
        ext = classifier.get_extractor("https://example.com")
        assert ext.config.timeout == 99
