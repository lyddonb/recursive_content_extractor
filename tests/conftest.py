"""Shared test fixtures."""

from __future__ import annotations

import pytest

from recursive_content_extractor.models import ExtractorConfig


@pytest.fixture
def default_config() -> ExtractorConfig:
    """Default extractor config for testing."""
    return ExtractorConfig(depth=1, timeout=10, rate_limit_delay=0)


@pytest.fixture
def sample_html() -> str:
    """Minimal HTML page for testing article extraction."""
    return """<!DOCTYPE html>
<html>
<head><title>Test Article</title></head>
<body>
  <article>
    <h1>Test Article Title</h1>
    <p>This is test article content with enough text to be meaningful.</p>
    <p>It has multiple paragraphs for extraction testing.</p>
    <a href="https://example.com/linked-page">A link</a>
    <a href="https://x.com/user/status/123456">A tweet</a>
    <a href="https://www.youtube.com/watch?v=dQw4w9WgXcQ">A video</a>
  </article>
</body>
</html>"""


@pytest.fixture
def sample_html_with_embeds() -> str:
    """HTML page with embedded tweets and iframes."""
    return """<!DOCTYPE html>
<html>
<head><title>Page With Embeds</title></head>
<body>
  <article>
    <p>Article with embeds.</p>
    <blockquote class="twitter-tweet">
      <a href="https://twitter.com/user/status/999">Tweet link</a>
    </blockquote>
    <iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ"></iframe>
    <div data-url="https://example.com/data-url-target"></div>
  </article>
</body>
</html>"""


@pytest.fixture
def fxtwitter_response() -> dict:
    """Mock FxTwitter API response."""
    return {
        "tweet": {
            "text": "Hello, this is a test tweet with some content.",
            "author": {
                "name": "Test User",
                "screen_name": "testuser",
            },
            "likes": 42,
            "retweets": 10,
            "replies": 5,
            "created_at": "2024-01-01T00:00:00Z",
            "urls": [
                {"url": "https://example.com/linked"},
            ],
        }
    }


@pytest.fixture
def syndication_response() -> dict:
    """Mock Twitter syndication API response."""
    return {
        "text": "A syndicated tweet.",
        "user": {
            "name": "Syndi User",
            "screen_name": "syndiuser",
        },
        "created_at": "2024-06-01T12:00:00Z",
        "entities": {
            "urls": [
                {"expanded_url": "https://example.com/expanded"},
            ],
        },
    }


@pytest.fixture
def oembed_response() -> dict:
    """Mock YouTube oEmbed response."""
    return {
        "title": "Test Video Title",
        "author_name": "Test Channel",
        "author_url": "https://www.youtube.com/@testchannel",
        "thumbnail_url": "https://i.ytimg.com/vi/test/maxresdefault.jpg",
    }
