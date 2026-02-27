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

---

## Longer-term (robustness & scale)

### 7. Persistent extraction state

Save extraction progress to disk so interrupted extractions can be resumed. Useful for deep crawls (depth >= 3) that may take a long time.

### 8. Rate limiting per domain

Currently rate limiting is a flat delay between batches. Implement per-domain rate limiting so high-value domains (Twitter, YouTube) get appropriate delays while other domains can proceed faster.

### 9. Content deduplication

Detect near-duplicate content across nodes (e.g., same article syndicated on multiple domains) using content hashing or fuzzy matching. Collapse duplicates in the output tree.

### 10. Plugin system

Allow third-party extractors to be installed as Python packages and auto-discovered via entry points (e.g., `[project.entry-points."rce.extractors"]`). Removes the need to manually call `register_extractor()`.

### 11. Create a MCP server wrapper

Add a MCP server that wraps this tool to be used by agents, especially coding agents like Claude Code, OpenAI's codex, Cursor, etc.

### 12. Publish to PyPI

Once stable, publish the package to PyPI so users can `pip install recursive-content-extractor` and get the `rce` CLI globally.

---

## Housekeeping (ongoing)

- Keep dependencies updated (`uv lock --upgrade`)
- Add test coverage reporting (`pytest-cov`, badge in README)
- Expand mypy strictness (`strict = true`) once all code is fully typed
- Add `py.typed` marker for downstream type checking
