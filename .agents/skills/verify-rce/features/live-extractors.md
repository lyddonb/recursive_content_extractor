# Live extractors

A user passes a YouTube video, GitHub repo, arXiv abstract, X post or PDF link, and rce routes it to a dedicated extractor that returns structured content (a transcript, a README, an abstract, the post text, the PDF text) instead of scraping the page as an article.

## Sub-features

- `LIVE-YT`: YouTube video gives type `youtube`, the video title, and the transcript.
- `LIVE-GH`: GitHub repo gives type `github`, `owner/repo - description`, and the README.
- `LIVE-ARXIV`: arXiv abstract gives type `arxiv`, the paper title, and the abstract.
- `LIVE-X`: a single X/Twitter post gives type `x_post` and the post text.
- `LIVE-PDF`: a PDF link gives type `pdf`, the text, and the links inside the PDF as children.

## How to get to it (user POV)

- `rce <youtube/github/arxiv/x url>` directly, or as a link on a page rce recurses into.
- `rce <url ending in .pdf>`.

## Driving it with control-rce

Preconditions: baseline. Network for everything but `LIVE-PDF` (`doctor` shows `network: ok`). Live runs don't need `--delay 0`.

- `LIVE-YT`: `control-rce run --name yt -- 'https://www.youtube.com/watch?v=dQw4w9WgXcQ' -d 0 -q -f json -o '{out}/result.json'`, then `control-rce check last --root-type youtube --root-title-prefix 'Rick Astley - Never Gonna Give You Up' --root-min-chars 1000`.
- `LIVE-GH`: `control-rce run --name gh -- 'https://github.com/astral-sh/uv' -d 0 -q -f json -o '{out}/result.json'`, then `control-rce check last --root-type github --root-title-prefix astral-sh/uv`.
- `LIVE-ARXIV`: `control-rce run --name arxiv -- 'https://arxiv.org/abs/1706.03762' -d 0 -q -f json -o '{out}/result.json'`, then `control-rce check last --root-type arxiv --root-title-prefix 'Attention Is All You Need'`.
- `LIVE-X`: `control-rce run --name x -- 'https://x.com/jack/status/20' -d 0 -q -f json -o '{out}/result.json'`, then `control-rce check last --root-type x_post --root-content-has 'just setting up my twttr'`.
- `LIVE-PDF` (offline, fixture site running): `control-rce run --name pdf -- '{site}/field-notes.pdf' -d 1 --delay 0 -q -f json -o '{out}/result.json'`, then `control-rce check last --has PDF --type PDF=pdf --has B --under B:PDF --children 1`.

## Gotchas

- These hit third-party services that rate-limit. GitHub falls back to raw README content when rate-limited, so a `github` node with a thinner title is still a pass. A 429 or empty content is "not verified", not "failed", unless the change touched that extractor.
- YouTube transcripts depend on `youtube-transcript-api`. `doctor` shows `youtube_extra`. YouTube blocks IPs that make many requests: then `LIVE-YT` fails `--root-min-chars` with about 120 chars of metadata and no transcript. That's "not verified" (blocked), not a regression. Confirm with `uv run python -c "from youtube_transcript_api import YouTubeTranscriptApi as Y; Y().fetch('dQw4w9WgXcQ')"`, which raises `IpBlocked`.
- X uses public FxTwitter and syndication APIs. Long threads and X Articles need `--browser`, which isn't mapped yet.
