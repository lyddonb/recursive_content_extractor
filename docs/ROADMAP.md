# Roadmap

Prioritized list of next work for the recursive content extractor.

---

## Medium-term (extend capabilities)

### 1. Caching layer

Add an optional disk cache (e.g., `diskcache` or simple file-based) so repeated extractions of the same URL don't re-fetch. Useful for development iteration and rate-limited APIs. Add `ExtractorConfig.cache_dir: str | None = None`.

### 2. Export formats

- **CSV export** -- flat table of all nodes (URL, title, type, content preview, depth)
- **OPML export** -- for importing content trees into RSS readers
- **SQLite export** -- for querying large extraction results

### 3. Streaming / progress callbacks

Add a callback mechanism so callers can receive progress updates during extraction (e.g., `on_node_extracted(node)`) rather than waiting for the full tree. Useful for UIs and long-running extractions.

### 4. Image extractor

Add an `ImageExtractor` that recognizes image URLs (by extension and `Content-Type` header), extracts available metadata (alt text, EXIF, OCR), and returns a proper `ContentType.IMAGE` node instead of silently falling through to the `ArticleExtractor` catch-all and returning empty content misclassified as `ContentType.ARTICLE`.

### 5. Graceful handling of unsupported file types

Add `Content-Type` header inspection to the classifier/fallback extractor so that binary files (`.docx`, `.zip`, `.xlsx`, etc.) are detected early and returned as `ContentType.UNKNOWN` with a descriptive message (e.g., "Unsupported file type: application/zip") rather than being silently misclassified as empty articles.

### 6. Reddit extractor

Add `RedditExtractor` for reddit.com URLs. Use Reddit's public JSON API (`url.json`) to extract posts and top comments without authentication.

### 7. Structured data extraction (`extruct`)

Enrich metadata and link discovery by parsing JSON-LD, Open Graph, microdata, and RDFa from pages. Currently `_extract_metadata` in `article.py` only reads `<meta>` tags — structured data contains richer author, date, related links, and entity information.

Tasks:
- Add `extruct` to optional dependencies in `pyproject.toml` (new `metadata` extra)
- Create `_extract_structured_data(html, url)` method in `ArticleExtractor`
- Merge structured data into `ExtractionResult.metadata` under a `structured_data` key
- Extract URLs found in JSON-LD `@id`, `url`, `mainEntityOfPage`, `relatedLink` fields and add to `links`
- Add tests with fixture HTML containing JSON-LD and microdata
- Graceful fallback when `extruct` is not installed

### 8. HTML table extraction

Preserve table structure from HTML pages and PDFs instead of flattening to plain text. Extracted tables should appear as markdown tables in content output.

Tasks:
- Add `_extract_tables(soup)` method to `ArticleExtractor` that converts `<table>` elements to markdown table format
- Integrate table markdown into content output (append after main text, under a `## Tables` heading)
- Add `include_tables: bool = True` to `ExtractorConfig`
- Update `PDFExtractor` to detect and preserve tabular regions using PyMuPDF's table detection (available in `fitz` via `page.find_tables()`)
- Add tests with fixture HTML containing tables and expected markdown output

### 9. RSS/Atom feed discovery

Discover feed URLs on pages and optionally follow them to find article links. Many sites expose `<link rel="alternate" type="application/rss+xml">` in their HTML head.

Tasks:
- Add `_discover_feeds(soup)` method to `ArticleExtractor` that finds `<link rel="alternate">` with RSS/Atom types
- Add `ContentType.FEED` to the `ContentType` enum
- Create `FeedExtractor` in `extractors/feed.py` that parses RSS/Atom XML and returns article links
- Add `feedparser` to optional dependencies in `pyproject.toml` (new `feeds` extra)
- Register `FeedExtractor` with priority 30 (below specialized extractors, above article fallback)
- Add `follow_feeds: bool = False` to `ExtractorConfig` (opt-in, since feeds can expand scope significantly)
- Add tests with fixture RSS/Atom XML

### 10. Content deduplication

Detect near-duplicate content across nodes (e.g., same article syndicated on multiple domains) using content fingerprinting. Collapse duplicates in the output tree.

Tasks:
- Add `_fingerprint_content(text)` function using simhash or MinHash in a new `dedup.py` module
- Store fingerprints in `RecursiveExtractor` alongside `_visited` set during extraction
- Before adding a child node, check fingerprint similarity against existing nodes
- When duplicate detected, add a `ContentType.DUPLICATE` type (or set `metadata["duplicate_of"] = original_url`) and skip content
- Add `deduplicate: bool = False` to `ExtractorConfig` (opt-in)
- Add CLI flag `--deduplicate`
- Add tests: identical content detected, near-duplicate detected, distinct content not flagged

---

## Longer-term (robustness & scale)

### 11. Persistent extraction state

Save extraction progress to disk so interrupted extractions can be resumed. Useful for deep crawls (depth >= 3) that may take a long time.

### 12. Rate limiting per domain

Currently rate limiting is a flat delay between batches. Implement per-domain rate limiting so high-value domains (Twitter, YouTube) get appropriate delays while other domains can proceed faster.

### 13. Plugin system

Allow third-party extractors to be installed as Python packages and auto-discovered via entry points (e.g., `[project.entry-points."rce.extractors"]`). Removes the need to manually call `register_extractor()`.

### 14. Create a MCP server wrapper

Add a MCP server that wraps this tool to be used by agents, especially coding agents like Claude Code, OpenAI's codex, Cursor, etc.

### 15. Publish to PyPI

Once stable, publish the package to PyPI so users can `pip install recursive-content-extractor` and get the `rce` CLI globally.

---

## Housekeeping (ongoing)

- Keep dependencies updated (`uv lock --upgrade`)
- Add test coverage reporting (`pytest-cov`, badge in README)
- Expand mypy strictness (`strict = true`) once all code is fully typed
- Add `py.typed` marker for downstream type checking
