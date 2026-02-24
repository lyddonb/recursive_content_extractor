# Completed

Items moved here from [ROADMAP.md](ROADMAP.md) after implementation.

---

### Integration tests with real network calls

Add a small `tests/test_integration.py` that makes real HTTP calls (marked with `@pytest.mark.network` so they're skipped by default). Validates the full pipeline actually works against live URLs like `https://example.com`.

```bash
uv run pytest -m network -v   # opt-in
```

**Completed:** `feat/integration-tests` branch — `tests/test_integration.py` with 5 tests (article, YouTube, arXiv, GitHub, recursive depth).

---

### GitHub extractor

Add `GitHubExtractor` for github.com URLs. Use the GitHub REST API to extract README content, issue/PR bodies, and discussion threads.

**Completed:** commit `9364234` — `GitHubExtractor` and `ArXivExtractor` added together.
