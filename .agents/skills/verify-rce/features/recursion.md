# Recursion and deduplication

A user gives rce one URL and a depth. rce extracts that page, then the pages it links to, down to the given depth, and returns them as a tree. A page reached twice, including through a cycle, a `#fragment` or an http/https or `www.` variant, appears once.

## Sub-features

- `REC-0`: depth 0 returns only the root.
- `REC-1`: depth 1 returns the root and its direct links.
- `REC-2`: depth 2 also returns links of links.
- `REC-CYCLE`: a link back to an already visited page is not extracted again.
- `REC-SELF`: a link to the same page with a `#fragment` is not a child.

## How to get to it (user POV)

- `rce <url>` (default depth 1).
- `rce <url> --depth N` or `-d N`.
- Library: `RecursiveExtractor(config=ExtractorConfig(depth=N)).extract(url)`. Not mapped here; the CLI is the primary surface.

## Driving it with control-rce

Preconditions: baseline; fixture site running. Each sub-feature is a `run` followed by a `check last`; `check` prints PASS or FAIL with the reasons.

- `REC-0`: `control-rce run --name rec0 -- '{site}/index.html' -d 0 --delay 0 -q -f json -o '{out}/result.json'`, then `control-rce check last --has ROOT --children 0`.
- `REC-1`: `control-rce run --name rec1 -- '{site}/index.html' -d 1 --delay 0 -q -f json -o '{out}/result.json'`, then `control-rce check last --has A --has B --has C --has DRAFT --has PDF --type PDF=pdf --lacks DEEP --children 5`.
- `REC-2`: `control-rce run --name rec2 -- '{site}/index.html' -d 2 --delay 0 -q -f json -o '{out}/result.json'`, then `control-rce check last --has A --has B --has C --has DRAFT --has PDF --has DEEP --under DEEP:A --children 5`.
- `REC-CYCLE`: right after `REC-2` (`a.html` links back to `index.html`), `control-rce check last --once ROOT`.
- `REC-SELF`: `control-rce run --name self -- '{site}/index.html' -d 1 --delay 0 -q -f json -o '{out}/result.json'`, then `control-rce check last --url-absent index.html --url-absent 'index.html#methods'`.

## Gotchas

- Children follow the order of links on the page: `a.html`, `b.html`, `field-notes.pdf`, `drafts/unpublished.html`, then `c.html`.
- At depth 2 the PDF links to `b.html`. `b.html` is already visited, so the PDF has no children.
- Without `--delay 0`, each level waits one second.
