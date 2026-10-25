# Link filters

A user can narrow which links rce follows: only links on the same domain as the page, not links matching a glob, or at most N links per page.

## Sub-features

- `FILTER-SAME`: `--same-domain` skips links on other hosts.
- `FILTER-EXCLUDE`: `--exclude <glob>` skips matching URLs. Repeatable.
- `FILTER-MAX`: `--max-links N` (`-l N`) caps the links followed per page.

## How to get to it (user POV)

- `rce <url> --same-domain`
- `rce <url> --exclude '<glob>'` (repeat for more patterns)
- `rce <url> --max-links N` or `-l N`

## Driving it with control-rce

Preconditions: baseline; fixture site running.

- `FILTER-SAME`: `control-rce run --name same -- '{site}/index.html' -d 1 --same-domain --delay 0 -q -f json -o '{out}/result.json'`, then `control-rce check last --has A --has B --has DRAFT --has PDF --lacks C --children 4`. `MARKER-C` is on `localhost`, a different domain.
- `FILTER-EXCLUDE`: `control-rce run --name excl -- '{site}/index.html' -d 1 --exclude '*drafts*' --delay 0 -q -f json -o '{out}/result.json'`, then `control-rce check last --has A --has B --has C --has PDF --lacks DRAFT --children 4`. An excluded link is dropped, not kept as a placeholder node.
- `FILTER-MAX`: `control-rce run --name max -- '{site}/index.html' -d 1 -l 2 --delay 0 -q -f json -o '{out}/result.json'`, then `control-rce check last --min-children 1 --max-children 2`.

## Gotchas

- `FILTER-MAX` is nondeterministic today. Links are collected into an unordered set and truncated before the self-link is removed, so `-l 2` follows a different pair on each run and sometimes yields only one child. Assert between 1 and N children, never which links.
- Domains compare host and port, after stripping `www.`. `127.0.0.1:<port>` and `localhost:<port>` are different domains, which is what the fixture relies on.
- The article extractor always drops links containing words like `login`, `privacy`, `terms`, `cookie` and image or script extensions, whatever the flags. Don't name new fixture pages with those words.
- Quote globs so the shell doesn't expand them.
