# CLAUDE.md

## Agent workflow

Use the `beau-mode` skill for any non-trivial task. It picks the playbook, the principles and the verification bar, so this file doesn't repeat them.

- Plans live outside the repo (scratch or notes) unless a multi-day effort needs `docs/plans/<slug>.md`, per beau-mode's Multi-phase plan playbook.
- Turn a repeated correction into a check or script with the `correct` skill, or a skill edit with `reflect`. Don't keep a lessons file.
- `main` is protected. Work on a branch and merge through a PR.

## Project Overview

**Recursive Content Extractor** (`rce`): A Python CLI/library that recursively extracts content from web pages, following embedded links (X/Twitter threads, YouTube videos, GitHub repos, arXiv papers, articles, PDFs) to build a content tree. Fully async (asyncio-based).

## Commands

```bash
# Setup (one-time)
uv sync --extra dev
uv run playwright install chromium   # optional, for --browser flag

# Run CLI
uv run rce <URL> [--depth N] [--format markdown|json|tree] [--browser] [--output FILE]

# Run checks
make check        # runs lint + format check + typecheck + test
make test         # uv run pytest -v (network tests: uv run pytest -m network)
make lint         # uv run ruff check src/ tests/
make format-check # uv run ruff format --check src/ tests/
make format       # uv run ruff format src/ tests/
make typecheck    # uv run mypy src/
```

## Pre-commit

`make check` runs lint, format check, mypy and tests. The pre-commit hook (`uv run pre-commit install`, once per clone) runs ruff on every commit. After moving or renaming the checkout, rebuild the venv (`rm -rf .venv && uv sync --extra dev`): its scripts hard-code the old path.

## Architecture

### Package Structure

```
src/recursive_content_extractor/
  __init__.py          # Public API re-exports
  models.py            # ContentType, ExtractionResult, ContentNode, ExtractorConfig
  classifier.py        # URLClassifier -- routes URLs to extractors by priority
  extractor.py         # RecursiveExtractor -- main orchestrator, recursion, cycle detection
  cli.py               # Click CLI entry point (rce command)
  writer.py            # Directory output: one file per node plus index files (-o dir/)
  exceptions.py        # ExtractorError hierarchy
  extractors/
    __init__.py         # Re-exports BaseExtractor
    base.py             # BaseExtractor ABC (shared HTTP client)
    article.py          # ArticleExtractor (trafilatura + BS4, priority -100, fallback)
    twitter.py          # TwitterExtractor (FxTwitter -> syndication -> Playwright, priority 50)
    youtube.py          # YouTubeExtractor (transcript-api -> page parsing, priority 50)
    github.py           # GitHubExtractor (REST API -> raw README fallback, priority 45)
    arxiv.py            # ArXivExtractor (Atom API -> HTML scraping, priority 45)
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
| `github.py` | `GitHubExtractor` | 45 | GitHub REST API for repo metadata and README -> raw.githubusercontent.com when rate-limited |
| `arxiv.py` | `ArXivExtractor` | 45 | arXiv Atom API for paper metadata -> abstract page HTML scraping |
| `pdf.py` | `PDFExtractor` | 40 | Downloads PDF, extracts text/links via PyMuPDF (fitz) |
| `article.py` | `ArticleExtractor` | -100 | Fallback catch-all. trafilatura for content, BeautifulSoup for links |
