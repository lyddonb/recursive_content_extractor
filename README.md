# Recursive Content Extractor

A Python tool that recursively extracts content from web pages, following embedded links to X/Twitter threads, YouTube videos, articles, and more — building a complete context tree from any URL.

## Features

- **Recursive link following** with configurable depth (default: 1)
- **Pluggable extractors** for different content types:
  - **X/Twitter** threads and posts
  - **YouTube** video transcripts
  - **Generic articles** (readability-based extraction)
  - **PDF** documents
  - Easily extensible with custom extractors
- **URL classification** — automatically routes each URL to the right extractor
- **Cycle detection** — visited-set prevents infinite loops
- **Rate limiting** — configurable delays between requests
- **Structured output** — JSON tree or flattened markdown

## Installation

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
# Install core dependencies
uv sync

# Install optional extras
uv sync --extra youtube   # YouTube transcript support
uv sync --extra browser   # Playwright for JS-rendered pages (X/Twitter, SPAs)
uv sync --extra pdf       # PDF document extraction
uv sync --extra all       # Everything above

# If using the browser extra, install Chromium
uv run playwright install chromium
```

## Integrations

No API keys are needed. Every extractor uses public, unauthenticated endpoints or local processing.

### X/Twitter

```bash
# No extra install needed for basic support; optional browser fallback:
uv sync --extra browser
uv run playwright install chromium
```

Three strategies are tried in order:

1. **FxTwitter API** — public proxy that returns tweet text and metadata. Works for most public tweets.
2. **Twitter syndication API** — public embed endpoint used as a fallback.
3. **Playwright headless browser** — requires the `browser` extra and the `--browser` CLI flag. Useful for tweets behind login walls or when the API proxies are blocked.

If all three fail (e.g. the tweet is deleted or fully private), the extractor returns an error.

### YouTube

```bash
uv sync --extra youtube   # installs youtube-transcript-api
```

Two strategies:

1. **youtube-transcript-api** — fetches captions/subtitles directly. Only works if the video uploader has enabled captions.
2. **Page HTML parsing** — scrapes the watch page as a fallback for transcript text.

Video metadata (title, author, thumbnail) is always fetched via YouTube's public oEmbed endpoint, which requires no API key.

### PDF

```bash
uv sync --extra pdf   # installs PyMuPDF (fitz)
```

Downloads the PDF locally and extracts text and hyperlinks using PyMuPDF. All processing is local — no external service is called. The extractor will raise an error if the `pdf` extra is not installed.

### Articles (default fallback)

No extra install needed — works with the base `uv sync`.

Acts as the catch-all extractor for any URL not matched by a higher-priority extractor. Uses [trafilatura](https://trafilatura.readthedocs.io/) for main content extraction with BeautifulSoup for link discovery. Embedded links — including Twitter/YouTube URLs found in iframes and `data-` attributes — are extracted and eligible for recursive following.

## Quick Start

```python
import asyncio
from recursive_content_extractor import RecursiveExtractor

async def main():
    extractor = RecursiveExtractor(depth=1)
    result = await extractor.extract("https://x.com/someuser/status/123456789")

    # Get structured JSON
    print(result.to_json())

    # Get flattened markdown (all content merged)
    print(result.to_markdown())

asyncio.run(main())
```

## CLI Usage

```bash
# Basic extraction
uv run rce https://example.com/article

# Set recursion depth
uv run rce https://example.com/article --depth 2

# Output as markdown
uv run rce https://example.com/article --format markdown

# Output as JSON
uv run rce https://example.com/article --format json --output result.json

# Use headless browser for JS-rendered pages
uv run rce https://x.com/user/status/123 --browser

# Verbose logging
uv run rce https://example.com/article --depth 2 --verbose
```

## Architecture

```
URL
 │
 ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Classifier  │────▶│  Extractor   │────▶│  ContentNode    │
│  (route URL) │     │  (pluggable) │     │  (text + links) │
└─────────────┘     └──────────────┘     └────────┬────────┘
                                                   │
                                          if depth > 0
                                                   │
                                                   ▼
                                          recurse on each
                                          extracted link
```

## Adding Custom Extractors

```python
from recursive_content_extractor import BaseExtractor, ExtractionResult, RecursiveExtractor

class MyExtractor(BaseExtractor):
    @staticmethod
    def can_handle(url: str) -> bool:
        return "mysite.com" in url

    async def extract(self, url: str) -> ExtractionResult:
        # Your extraction logic here
        return ExtractionResult(
            url=url,
            title="Page Title",
            content="Extracted text...",
            links=["https://found-link.com"],
            metadata={"custom": "data"}
        )

# Register it
extractor = RecursiveExtractor(depth=1)
extractor.register_extractor(MyExtractor, priority=10)
```

## Configuration

```python
from recursive_content_extractor import RecursiveExtractor, ExtractorConfig

config = ExtractorConfig(
    depth=2,                    # Max recursion depth
    rate_limit_delay=1.0,       # Seconds between requests
    max_links_per_page=20,      # Cap on links to follow per page
    timeout=30,                 # Request timeout in seconds
    use_browser=False,          # Use Playwright for JS rendering
    max_concurrent_requests=5,  # Concurrent request limit
    include_patterns=["*"],     # URL patterns to follow
    exclude_patterns=[],        # URL patterns to skip
)

extractor = RecursiveExtractor(config=config)
```

## Output Format

The tool produces a tree of `ContentNode` objects:

```json
{
  "url": "https://example.com/article",
  "title": "Article Title",
  "content_type": "article",
  "content": "Full extracted text...",
  "metadata": { "author": "...", "date": "..." },
  "children": [
    {
      "url": "https://x.com/user/status/123",
      "title": "X Thread",
      "content_type": "x_thread",
      "content": "Thread text...",
      "children": []
    },
    {
      "url": "https://youtube.com/watch?v=abc",
      "title": "Video Title",
      "content_type": "youtube",
      "content": "Transcript...",
      "children": []
    }
  ]
}
```

## Development

```bash
# Install all dependencies including dev tools
uv sync --extra dev

# Run all checks (lint + typecheck + tests)
make check

# Individual commands
make test         # uv run pytest -v
make lint         # uv run ruff check src/ tests/
make format       # uv run ruff format src/ tests/
make typecheck    # uv run mypy src/
```

## License

MIT
