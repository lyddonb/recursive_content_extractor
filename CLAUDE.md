# CLAUDE.md

## Project Overview

**Recursive Content Extractor** (`rce`): A Python CLI/library that recursively extracts content from web pages, following embedded links (X/Twitter threads, YouTube videos, articles, PDFs) to build a content tree. Fully async (asyncio-based).

## Commands

```bash
# Setup (one-time)
uv sync --extra dev
uv run playwright install chromium   # optional, for --browser flag

# Run CLI
uv run rce <URL> [--depth N] [--format markdown|json|tree] [--browser] [--output FILE]

# Run checks
make check        # runs lint + typecheck + test
make test         # uv run pytest -v
make lint         # uv run ruff check src/ tests/
make format       # uv run ruff format src/ tests/
make typecheck    # uv run mypy src/
```

## Pre-commit Checklist

Before committing, ensure all pass:
1. `uv run ruff check src/ tests/` -- no lint errors
2. `uv run ruff format --check src/ tests/` -- formatting clean
3. `uv run mypy src/` -- no type errors
4. `uv run pytest` -- all tests pass

Or just run `make check` to do all four.

## Architecture

### Package Structure

```
src/recursive_content_extractor/
  __init__.py          # Public API re-exports
  models.py            # ContentType, ExtractionResult, ContentNode, ExtractorConfig
  classifier.py        # URLClassifier -- routes URLs to extractors by priority
  extractor.py         # RecursiveExtractor -- main orchestrator, recursion, cycle detection
  cli.py               # Click CLI entry point (rce command)
  exceptions.py        # ExtractorError hierarchy
  extractors/
    __init__.py         # Re-exports BaseExtractor
    base.py             # BaseExtractor ABC (shared HTTP client)
    article.py          # ArticleExtractor (trafilatura + BS4, priority -100, fallback)
    twitter.py          # TwitterExtractor (FxTwitter -> syndication -> Playwright, priority 50)
    youtube.py          # YouTubeExtractor (transcript-api -> page parsing, priority 50)
    pdf.py              # PDFExtractor (PyMuPDF, priority 40)
tests/
examples/
```

### Core Flow

`URL -> URLClassifier -> specific Extractor -> ExtractionResult -> ContentNode tree`

### Import Convention

All imports use fully-qualified absolute paths: `from recursive_content_extractor.models import ExtractorConfig`

### Key Patterns

- **Strategy pattern**: Each extractor tries multiple methods in order (`_try_*` methods), falling back gracefully.
- **Shared HTTP client**: `BaseExtractor` provides `_get_client()` / `close()` -- all subclasses inherit it.
- **Custom extractors**: Register via `RecursiveExtractor.register_extractor(MyExtractor, priority=N)`.
- **Configurable concurrency**: `ExtractorConfig.max_concurrent_requests` controls the semaphore.

### Extractors (priority order)

| Module | Class | Priority | Strategy |
|---|---|---|---|
| `twitter.py` | `TwitterExtractor` | 50 | FxTwitter API -> syndication API -> Playwright (if `--browser`) |
| `youtube.py` | `YouTubeExtractor` | 50 | youtube-transcript-api -> page HTML parsing; metadata via oEmbed |
| `pdf.py` | `PDFExtractor` | 40 | Downloads PDF, extracts text/links via PyMuPDF (fitz) |
| `article.py` | `ArticleExtractor` | -100 | Fallback catch-all. trafilatura for content, BeautifulSoup for links |
