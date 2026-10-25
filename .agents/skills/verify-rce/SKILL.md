---
name: verify-rce
description: Prove a change to the rce CLI (recursive content extractor) works by running the real CLI against a local fixture site and live URLs, with captured evidence. Use before saying an rce change is done, when asked to verify, prove or smoke-test rce, or when verify-work needs a way to drive this repo.
---

# Verify rce

`rce` is a CLI: a user passes a URL and gets back a content tree (markdown, JSON or tree text, to stdout, a file or a directory). Verify by running the real CLI through `control-rce`, which serves an offline fixture site, captures evidence and cleans up. Unit tests (`make check`) are not proof of behavior.

`control-rce` lives at `.agents/skills/verify-rce/scripts/control-rce` (relative to the repo root). Every subcommand has `--help` and `--json`.

## Launch

Shell state doesn't survive between tool calls, so make every command self-contained: call the script by its path and pass `--run <id>` (or prefix `RCE_VERIFY_RUN=<id>`) on each one. Pick one id per verification, e.g. the branch name.

```bash
.agents/skills/verify-rce/scripts/control-rce site start --run my-branch --json   # prints base_url
```

Ready when `site start` prints `base_url`. It's idempotent. The site is a short-lived `python -m http.server` on a free port, bound to 127.0.0.1. The same server is also reachable as `localhost:<port>`, which rce treats as a different domain.

The recipes below write `control-rce` for the script path and leave out `--run`. Add both.

## Doctor

Run first, and again when anything looks off:

```bash
.agents/skills/verify-rce/scripts/control-rce doctor --run my-branch   # add --offline to skip the network check
```

`FAIL` on `venv` means the checkout moved; its fix is printed. `warn` on `network` means live features can't be verified: report them as not verified, never as passed.

## Drive

Each recipe is a `run` followed by a `check`:

```bash
control-rce run --name depth1 -- '{site}/index.html' -d 1 --delay 0 -q -f json -o '{out}/result.json'
control-rce check last --has A --has DRAFT --lacks DEEP --children 5
```

- `run` executes `uv run rce <args>`. `{site}` is the fixture base URL, `{other}` the same server as `localhost`, `{out}` this run's evidence folder. It prints `evidence_dir` and exits with rce's exit code, so a run that is meant to fail exits non-zero.
- `check last` asserts on the latest run's evidence and prints PASS, or FAIL with every reason; it exits 1 on failure. Markers drop the `MARKER-` prefix. See `control-rce check --help` for every assertion, including `--stdout-has` and `--file-exists` for runs without JSON output.
- `outline last` prints the node tree (type, URL, marker, error) when a check fails and you need to see why.
- Pass `--delay 0` against the fixture and `-q` to keep logs out of stdout.
- Children come back in page order, so `--children` counts and `--under` are stable.
- rce exits 1 when the root URL fails and 0 otherwise, even when some child pages fail. Assert it with `--exit-code`.

The feature map in [features/README.md](features/README.md) has the recipe for each user-facing feature and the fixture page layout.

To run the whole map (or part of it) in one step, which is the right default for a change that touches recursion, filtering or output:

```bash
.agents/skills/verify-rce/scripts/run-feature-map --run my-branch            # all 18 checks, about 15s
.agents/skills/verify-rce/scripts/run-feature-map --run my-branch --offline  # skip the network recipes
.agents/skills/verify-rce/scripts/run-feature-map --run my-branch --only OUT # one feature
```

It runs the recipes exactly as written in `features/*.md`, so a recipe that drifts from the CLI fails here. It starts and cleans up the site itself. When you add or change a recipe, rerun it.

## Evidence

Each `run` writes `.verify/<run>/evidence/NN-<name>/` with `command.txt`, `stdout.txt`, `stderr.txt`, `exit_code.txt` and any output written to `{out}`. Proof is the command plus the `check` result: name the evidence folder and quote the PASS line, or the FAIL reasons. A live feature without network is "not verified", with the doctor line as the reason.

## Cleanup

```bash
.agents/skills/verify-rce/scripts/control-rce cleanup --run my-branch   # stops this run's server, keeps evidence
```

Cleanup never kills a process it didn't start: it checks the recorded pid's command line first. Evidence and `site.log` stay under `.verify/<run>/` (git-ignored) until you delete them.

## Changing the fixtures

Pages are in `fixtures/site/`. `{other}` in a page is replaced with the `localhost` origin at start, and `field-notes.pdf` is generated at start (see `PDF_SCRIPT` in `control-rce`). Give every new page a unique `MARKER-*` phrase and add it to the layout in `features/README.md`.
