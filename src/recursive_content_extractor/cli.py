"""CLI for the Recursive Content Extractor."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table
from rich.tree import Tree

from recursive_content_extractor.extractor import RecursiveExtractor
from recursive_content_extractor.models import ContentNode, ContentType, ExtractorConfig

console = Console()


def setup_logging(verbose: bool, quiet: bool) -> None:
    if quiet:
        level = logging.WARNING
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%H:%M:%S]",
        handlers=[RichHandler(rich_tracebacks=True, show_path=verbose)],
    )
    if not verbose:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("playwright").setLevel(logging.WARNING)


@click.command()
@click.argument("url")
@click.option(
    "--depth",
    "-d",
    default=1,
    type=int,
    help="Recursion depth (0=root only, 1=root+links, etc.)",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    default="markdown",
    type=click.Choice(["markdown", "json", "tree"]),
    help="Output format",
)
@click.option(
    "--output",
    "-o",
    default=None,
    type=click.Path(),
    help="Write output to file, or to a directory if path ends with / or is an existing dir",
)
@click.option(
    "--browser",
    "-b",
    is_flag=True,
    default=False,
    help="Use headless browser for JS-rendered pages (requires playwright)",
)
@click.option(
    "--max-links",
    "-l",
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
    "--retries",
    default=2,
    type=int,
    help="Number of retries for transient HTTP failures (0 to disable)",
)
@click.option(
    "--retry-backoff",
    default=0.5,
    type=float,
    help="Backoff factor for retries (delay = factor * 2^attempt)",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Enable verbose/debug logging",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    default=False,
    help="Suppress log output (only show warnings and errors)",
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
    retries: int,
    retry_backoff: float,
    verbose: bool,
    quiet: bool,
):
    """Recursively extract content from a URL and its linked pages.

    Follows embedded X/Twitter threads, YouTube videos, articles,
    and PDFs up to the specified depth.

    Examples:

        rce https://example.com/article

        rce https://x.com/user/status/123 --depth 2 --browser

        rce https://example.com --format json -o result.json
    """
    if verbose and quiet:
        raise click.UsageError("--verbose and --quiet are mutually exclusive.")

    setup_logging(verbose, quiet)

    config = ExtractorConfig(
        depth=depth,
        use_browser=browser,
        max_links_per_page=max_links,
        rate_limit_delay=delay,
        follow_same_domain_only=same_domain,
        exclude_patterns=list(exclude),
        max_retries=retries,
        retry_backoff_factor=retry_backoff,
    )

    extractor = RecursiveExtractor(config=config)

    console.rule("[bold]Recursive Content Extractor[/bold]")
    console.print(
        f"[bold]URL:[/bold] {url}  "
        f"[dim]depth={depth}  browser={browser}  max_links={max_links}[/dim]"
    )
    console.print()

    result = asyncio.run(extractor.extract(url))

    if output_format == "json":
        formatted = result.to_json(indent=2)
    elif output_format == "tree":
        formatted = _format_tree_plain(result)
    else:
        formatted = result.to_markdown()

    if output:
        path = Path(output)
        if output.endswith("/") or path.is_dir():
            from recursive_content_extractor.writer import write_tree_to_directory

            path.mkdir(parents=True, exist_ok=True)
            write_tree_to_directory(result, path, output_format)
            console.print(f"\nWritten to {path}/ ({result.total_nodes} files)")
        else:
            path.write_text(formatted, encoding="utf-8")
            console.print(f"\nWritten to {path} ({len(formatted):,} chars)")
    elif output_format == "tree":
        console.print(_format_rich_tree(result))
    else:
        console.print(formatted)

    _print_summary_table(result, output_format, depth)

    # Output is still written above so the error node can be inspected; only a
    # failed root fails the run, since dead child links are normal in a crawl.
    if result.content_type == ContentType.ERROR:
        click.echo(f"Error: could not extract {url}: {result.error}", err=True)
        raise click.exceptions.Exit(1)


def _print_summary_table(result: ContentNode, output_format: str, depth: int) -> None:
    """Print a Rich summary table after extraction."""
    console.print()
    table = Table(title="Extraction Summary", show_header=False, border_style="dim")
    table.add_column("Metric", style="bold")
    table.add_column("Value")
    table.add_row("Total nodes", str(result.total_nodes))
    table.add_row("Total content", f"{result.total_content_length:,} chars")
    table.add_row("Max depth", str(depth))
    table.add_row("Format", output_format)
    console.print(table)


def _format_tree_plain(node: ContentNode, indent: int = 0) -> str:
    """Format a ContentNode tree as plain text (for file output)."""
    lines = []
    prefix = "  " * indent
    connector = "\u251c\u2500\u2500 " if indent > 0 else ""

    status = "\u2713" if node.content else "\u2717"
    content_preview = (
        node.content[:60].replace("\n", " ") + "..."
        if node.content and len(node.content) > 60
        else node.content.replace("\n", " ")
        if node.content
        else "[empty]"
    )

    lines.append(
        f"{prefix}{connector}[{status}] {node.content_type.value}: {node.title or node.url}"
    )
    lines.append(f"{prefix}    URL: {node.url}")
    lines.append(f"{prefix}    Content: {content_preview}")

    if node.error:
        lines.append(f"{prefix}    Error: {node.error}")

    for child in node.children:
        lines.append(_format_tree_plain(child, indent + 1))

    return "\n".join(lines)


def _format_rich_tree(node: ContentNode) -> Tree:
    """Format a ContentNode tree using Rich Tree for colored output."""
    status = "[green]\u2713[/green]" if node.content else "[red]\u2717[/red]"
    label = f"{status} [bold]{node.content_type.value}[/bold]: {node.title or node.url}"
    tree = Tree(label)

    tree.add(f"[dim]URL:[/dim] {node.url}")

    if node.content:
        preview = node.content[:80].replace("\n", " ")
        if len(node.content) > 80:
            preview += "..."
        tree.add(f"[dim]Content:[/dim] {preview}")
    else:
        tree.add("[dim]Content:[/dim] [italic]empty[/italic]")

    if node.error:
        tree.add(f"[red]Error:[/red] {node.error}")

    for child in node.children:
        child_tree = _format_rich_tree(child)
        tree.children.append(child_tree)

    return tree
