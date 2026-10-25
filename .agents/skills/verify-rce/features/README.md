# rce verification map

The maintained record of what an rce user can do and how to prove each thing works. Read this index, then use the matching feature file as the recipe.

## Baseline preconditions

- `control-rce doctor` reports `ready`.
- A fixture site started by this run: `control-rce site start`. Never drive a server this run didn't start.
- `RCE_VERIFY_RUN` set to a unique id when more than one verification runs at once.
- Network only for [live extractors](./live-extractors.md).

## Fixture layout

| Page | Marker | Links to |
|---|---|---|
| `index.html` | `MARKER-ROOT` | `a.html`, `b.html`, `field-notes.pdf`, `drafts/unpublished.html`, `{other}/c.html`, `index.html#methods` |
| `a.html` | `MARKER-A` | `deep.html`, `index.html` |
| `b.html` | `MARKER-B` | none |
| `deep.html` | `MARKER-DEEP` | none |
| `c.html` (served as `localhost`) | `MARKER-C` | none |
| `drafts/unpublished.html` | `MARKER-DRAFT` | none |
| `field-notes.pdf` (generated) | `MARKER-PDF` | `b.html` |

## Driving conventions

- Run rce only through `control-rce run --name <label> -- <rce args>`, with `--delay 0 -q` against the fixture.
- Use `-f json -o '{out}/result.json'` for anything you assert on, then `control-rce check last`.
- Assert on the set of markers and types. Child order is not stable.
- Treat every command as literal. Keep the quotes around `{site}`, `{out}` and globs.

## Proof and skip reporting

- Proof is the evidence folder plus the `check` PASS line.
- For errors, use `check --root-error`. rce exits 0 even when a URL fails.
- Report a live feature as not verified, with the doctor output, when the network is down. Don't substitute a fixture run for a live one.
- `--browser` (Playwright) isn't mapped yet. Report it as not verified.

## Feature entry contract

Each feature file starts with an H1 and one paragraph of user-visible behavior, then exactly these H2s in order: `Sub-features`, `How to get to it (user POV)`, `Driving it with control-rce`, `Gotchas`. Keep implementation details out.

## Features

- [Recursion and deduplication](./recursion.md) covers depth, cycles and self-links.
- [Link filters](./link-filters.md) covers `--same-domain`, `--exclude` and `--max-links`.
- [Output](./output.md) covers markdown, JSON and tree formats, file and directory output, and error reporting.
- [Live extractors](./live-extractors.md) covers YouTube, GitHub, arXiv, X and PDF.
