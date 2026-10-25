# Output

A user picks how the tree comes back: markdown (default), JSON or an indented tree. They can print it, write it to one file, or write a directory with one file per page plus index files. A page that fails shows up as an error node with the reason.

## Sub-features

- `OUT-MD`: markdown to stdout (default).
- `OUT-JSON`: `-f json`, nested nodes with `url`, `title`, `content_type`, `content`, `metadata`, `depth`, `error` and `children`.
- `OUT-TREE`: `-f tree`, an indented tree with a status mark per node.
- `OUT-FILE`: `-o <file>` writes the formatted output to one file.
- `OUT-DIR`: `-o <dir>/` writes one folder per page plus `INDEX.md` and `index.json`.
- `OUT-ERROR`: an unreachable URL becomes a node with `content_type` `error` and a filled `error` field.

## How to get to it (user POV)

- `rce <url>`, `rce <url> -f json`, `rce <url> -f tree`
- `rce <url> -o result.json` (file), `rce <url> -o out/` (directory: trailing slash or an existing directory)

## Driving it with control-rce

Preconditions: baseline; fixture site running.

- `OUT-MD`: `control-rce run --name md -- '{site}/index.html' -d 0 --delay 0 -q`, then `control-rce check last --stdout-has '**Source:** http://127.0.0.1:' --stdout-has MARKER-ROOT`.
- `OUT-JSON` and `OUT-FILE`: `control-rce run --name json -- '{site}/index.html' -d 1 --delay 0 -q -f json -o '{out}/result.json'`, then `control-rce check last --root-url-prefix http://127.0.0.1: --root-type article --children 5`. The prefix check proves the URL was not rewritten to https.
- `OUT-TREE`: `control-rce run --name tree -- '{site}/index.html' -d 1 --delay 0 -q -f tree`, then `control-rce check last --stdout-has 'article: Anemone Counts' --stdout-has 'Extraction Summary'`.
- `OUT-DIR`: `control-rce run --name dir -- '{site}/index.html' -d 1 --delay 0 -q -f markdown -o '{out}/tree/'`, then `control-rce check last --file-exists tree/INDEX.md --file-exists tree/index.json --file-exists tree/content.md --file-exists tree/anemone-counts/content.md --file-exists tree/barnacle-zones/content.md --file-exists tree/crab-census/content.md --file-exists tree/unpublished-draft/content.md --file-exists tree/fixture-pdf-tidepool-field-notes/content.md`. Folder names come from page titles.
- `OUT-ERROR`: `control-rce run --name refused -- 'http://127.0.0.1:1/' -d 0 --delay 0 -q -f json -o '{out}/result.json'`, then `control-rce check last --root-type error --root-error 'All connection attempts failed'`.

## Gotchas

- rce exits 0 even for `OUT-ERROR`. The proof is the `error` field, not the exit code. It takes about two seconds because rce retries twice.
- The summary table always prints to stdout after the output, even with `-q` and even with `-f json` to stdout. Use `-o` when you need clean JSON.
- `-f tree` to stdout is Rich-rendered and wraps at terminal width. Match on short substrings.
