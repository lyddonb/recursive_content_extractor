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

```bash
pip install -r requirements.txt

# For YouTube transcript support
pip install yt-dlp

# For browser-rendered pages (X/Twitter, SPAs)
playwright install chromium
```

## Quick Start

```python
from extractor import RecursiveExtractor

extractor = RecursiveExtractor(depth=1)
result = extractor.extract("https://x.com/someuser/status/123456789")

# Get structured JSON
print(result.to_json())

# Get flattened markdown (all content merged)
print(result.to_markdown())
```

## CLI Usage

```bash
# Basic extraction
python cli.py https://example.com/article

# Set recursion depth
python cli.py https://example.com/article --depth 2

# Output as markdown
python cli.py https://example.com/article --format markdown

# Output as JSON
python cli.py https://example.com/article --format json --output result.json

# Use headless browser for JS-rendered pages
python cli.py https://x.com/user/status/123 --browser

# Verbose logging
python cli.py https://example.com/article --depth 2 --verbose
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
from extractors.base import BaseExtractor, ExtractionResult

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
from extractor import RecursiveExtractor, ExtractorConfig

config = ExtractorConfig(
    depth=2,                    # Max recursion depth
    rate_limit_delay=1.0,       # Seconds between requests
    max_links_per_page=20,      # Cap on links to follow per page
    timeout=30,                 # Request timeout in seconds
    use_browser=False,          # Use Playwright for JS rendering
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

## License

MIT
