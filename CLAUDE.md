# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Recursive Content Extractor: a Python CLI/library that recursively extracts content from web pages, following embedded links (X/Twitter threads, YouTube videos, articles, PDFs) to build a content tree. Fully async (asyncio-based).

## Commands

```bash
# Install dependencies
pip install -r requirements.txt
playwright install chromium  # optional, for JS-rendered pages

# Run CLI
python cli.py <URL> [--depth N] [--format markdown|json|tree] [--browser] [--output FILE]

# Run examples
python examples.py          # basic examples only
python examples.py --all    # includes network-dependent examples
```

There are no tests, linter, or build system configured yet.

## Architecture

**Import note:** `classifier.py` imports extractors as `from extractors import ...` and `from extractors.article import ...`. The root `__init__.py` defines `BaseExtractor` and acts as the `extractors` package. Other modules (`cli.py`, `extractor.py`) import siblings as top-level modules (e.g., `from extractor import RecursiveExtractor`).

### Core Flow

`URL -> URLClassifier (classifier.py) -> specific Extractor -> ExtractionResult -> ContentNode tree`

- **`extractor.py`** — `RecursiveExtractor` is the main orchestrator. Manages recursion, cycle detection (visited set), concurrency (semaphore of 5), URL filtering (include/exclude patterns), and rate limiting. Entry point: `extract(url)` returns a `ContentNode` tree.
- **`classifier.py`** — `URLClassifier` routes URLs to extractors by checking `can_handle()` in priority order (highest first). Lazily instantiates and caches extractor instances.
- **`models.py`** — All data models: `ContentType` (enum), `ExtractionResult` (single extraction output), `ContentNode` (tree node with `to_json()`/`to_markdown()`/`flatten()`), `ExtractorConfig` (all settings).
- **`__init__.py`** — Defines `BaseExtractor` ABC. Custom extractors must implement `can_handle(url) -> bool` (static) and `async extract(url) -> ExtractionResult`. Optional `priority() -> int` (higher = checked first).

### Extractors (priority order)

| Module | Class | Priority | Strategy |
|---|---|---|---|
| `twitter.py` | `TwitterExtractor` | 50 | FxTwitter API -> syndication API -> Playwright (if `--browser`) |
| `youtube.py` | `YouTubeExtractor` | 50 | youtube-transcript-api -> page HTML parsing; metadata via oEmbed |
| `pdf.py` | `PDFExtractor` | 40 | Downloads PDF, extracts text/links via PyMuPDF (fitz) |
| `article.py` | `ArticleExtractor` | -100 | Fallback catch-all. trafilatura for content, BeautifulSoup for link discovery (a tags, iframes, embedded tweets, data-* attrs) |

### Key Patterns

- **Strategy pattern in extractors**: Each extractor tries multiple extraction methods in order, falling back gracefully. Check `_try_*` methods.
- **All extractors share an httpx.AsyncClient** per instance (lazy init, cached).
- **Custom extractors** are registered via `RecursiveExtractor.register_extractor(MyExtractor, priority=N)` — they plug into the classifier's priority chain.
- **ContentNode.to_markdown()** flattens the entire tree into a single document; `to_json()` preserves the tree structure.
