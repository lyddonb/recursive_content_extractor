#!/usr/bin/env python3
"""CLI for the Recursive Content Extractor.

Usage:
    python cli.py https://example.com/article
    python cli.py https://x.com/user/status/123 --depth 2 --browser
    python cli.py https://example.com --format json --output result.json
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

try:
    import click
except ImportError:
    print("Click not installed. Run: pip install click")
    print("Or use the Python API directly — see README.md")
    sys.exit(1)

from extractor import RecursiveExtractor
from models import ExtractorConfig


def setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # Quiet down noisy libraries
    if not verbose:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("playwright").setLevel(logging.WARNING)


@click.command()
@click.argument("url")
@click.option(
    "--depth", "-d",
    default=1,
    type=int,
    help="Recursion depth (0=root only, 1=root+links, etc.)",
)
@click.option(
    "--format", "-f", "output_format",
    default="markdown",
    type=click.Choice(["markdown", "json", "tree"]),
    help="Output format",
)
@click.option(
    "--output", "-o",
    default=None,
    type=click.Path(),
    help="Write output to file instead of stdout",
)
@click.option(
    "--browser", "-b",
    is_flag=True,
    default=False,
    help="Use headless browser for JS-rendered pages (requires playwright)",
)
@click.option(
    "--max-links", "-l",
    default=20,
    type=int,
    help="Max links to follow per page",
)
@click.option(
    "--delay",
    default=1.0,
    type=float,
    help="Rate limit delay between requests (seconds)",
)
@click.option(
    "--same-domain",
    is_flag=True,
    default=False,
    help="Only follow links on the same domain",
)
@click.option(
    "--exclude",
    multiple=True,
    help="URL patterns to exclude (glob syntax, repeatable)",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    default=False,
    help="Enable verbose/debug logging",
)
def main(
    url: str,
    depth: int,
    output_format: str,
    output: str | None,
    browser: bool,
    max_links: int,
    delay: float,
    same_domain: bool,
    exclude: tuple[str, ...],
    verbose: bool,
):
    """Recursively extract content from a URL and its linked pages.

    Follows embedded X/Twitter threads, YouTube videos, articles,
    and PDFs up to the specified depth.

    Examples:

        # Extract an article and its embedded links
        python cli.py https://example.com/article

        # Deep extraction with browser rendering
        python cli.py https://x.com/user/status/123 --depth 2 --browser

        # Save as JSON
        python cli.py https://example.com --format json -o result.json
    """
    setup_logging(verbose)

    config = ExtractorConfig(
        depth=depth,
        use_browser=browser,
        max_links_per_page=max_links,
        rate_limit_delay=delay,
        follow_same_domain_only=same_domain,
        exclude_patterns=list(exclude),
    )

    extractor = RecursiveExtractor(config=config)

    click.echo(f"Extracting: {url}")
    click.echo(f"Depth: {depth} | Browser: {browser} | Max links/page: {max_links}")
    click.echo("---")

    # Run the async extraction
    result = asyncio.run(extractor.extract(url))

    # Format output
    if output_format == "json":
        formatted = result.to_json(indent=2)
    elif output_format == "tree":
        formatted = _format_tree(result)
    else:
        formatted = result.to_markdown()

    # Output
    if output:
        path = Path(output)
        path.write_text(formatted, encoding="utf-8")
        click.echo(f"\nWritten to {path} ({len(formatted):,} chars)")
    else:
        click.echo(formatted)

    # Summary
    click.echo("\n---")
    click.echo(f"Total nodes: {result.total_nodes}")
    click.echo(f"Total content: {result.total_content_length:,} chars")


def _format_tree(node, indent: int = 0) -> str:
    """Format a ContentNode tree as an indented tree view."""
    lines = []
    prefix = "  " * indent
    connector = "├── " if indent > 0 else ""

    status = "✓" if node.content else "✗"
    content_preview = (
        node.content[:60].replace("\n", " ") + "..."
        if node.content and len(node.content) > 60
        else node.content.replace("\n", " ") if node.content else "[empty]"
    )

    lines.append(
        f"{prefix}{connector}[{status}] {node.content_type.value}: "
        f"{node.title or node.url}"
    )
    lines.append(f"{prefix}    URL: {node.url}")
    lines.append(f"{prefix}    Content: {content_preview}")

    if node.error:
        lines.append(f"{prefix}    Error: {node.error}")

    for child in node.children:
        lines.append(_format_tree(child, indent + 1))

    return "\n".join(lines)


if __name__ == "__main__":
    main()
