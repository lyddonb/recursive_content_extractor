# CLAUDE.md

## Workflow Orchestration

### 1. Plan Node Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately - don't keep pushing
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity

### 2. Subagent Strategy
- Use subagents liberally to keep main context window clean
- Offload research, exploration, and parallel analysis to subagents
- For complex problems, throw more compute at it via subagents
- One task per subagent for focused execution

### 3. Self-Improvement Loop
- After ANY correction from the user: update `tasks/lessons.md` with the pattern
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until mistake rate drops
- Review lessons at session start for relevant project

### 4. Verification Before Done
- Never mark a task complete without proving it works
- Diff behavior between main and your changes when relevant
- Ask yourself: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness

### 5. Demand Elegance (Balanced)
- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant solution"
- Skip this for simple, obvious fixes - don't over-engineer
- Challenge your own work before presenting it

### 6. Autonomous Bug Fixing
- When given a bug report: just fix it. Don't ask for hand-holding
- Point at logs, errors, failing tests - then resolve them
- Zero context switching required from the user
- Go fix failing CI tests without being told how

## Task Management

1. **Plan First**: Write plan to `tasks/todo.md` with checkable items
2. **Verify Plan**: Check in before starting implementation
3. **Track Progress**: Mark items complete as you go
4. **Explain Changes**: High-level summary at each step
5. **Document Results**: Add review section to `tasks/todo.md`
6. **Capture Lessons**: Update `tasks/lessons.md` after corrections

## Core Principles

- **Simplicity First**: Make every change as simple as possible. Impact minimal code.
- **No Laziness**: Find root causes. No temporary fixes. Senior developer standards.
- **Minimal Impact**: Changes should only touch what's necessary. Avoid introducing bugs.

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
