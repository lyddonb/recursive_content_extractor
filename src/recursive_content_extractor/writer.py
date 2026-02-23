"""Directory-based output writer for recursive extractions.

Writes each ContentNode as its own file within a directory structure
that mirrors the content hierarchy, with index files mapping relationships.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from recursive_content_extractor.models import ContentNode


FORMAT_EXTENSIONS: dict[str, str] = {
    "markdown": ".md",
    "json": ".json",
    "tree": ".txt",
}


def sanitize_filename(name: str, max_length: int = 80) -> str:
    """Convert a title or URL into a filesystem-safe directory name.

    Prefers title text; falls back to URL path segments; final fallback "untitled".
    """
    if not name or not name.strip():
        return "untitled"

    # If it looks like a URL, extract path segments
    if name.startswith(("http://", "https://")):
        parsed = urlparse(name)
        path_parts = [p for p in parsed.path.strip("/").split("/") if p]
        if path_parts:
            name = "-".join(path_parts)
        elif parsed.netloc:
            name = parsed.netloc
        else:
            return "untitled"

    # Lowercase, replace whitespace with hyphens
    name = name.lower()
    name = re.sub(r"\s+", "-", name)
    # Strip non-allowed chars
    name = re.sub(r"[^a-z0-9_-]", "", name)
    # Collapse consecutive hyphens
    name = re.sub(r"-{2,}", "-", name)
    # Strip leading/trailing hyphens
    name = name.strip("-")
    # Truncate
    name = name[:max_length].rstrip("-")

    return name or "untitled"


def _resolve_collision(name: str, used: set[str]) -> str:
    """Append -2, -3, etc. if name already exists in used set."""
    if name not in used:
        used.add(name)
        return name
    counter = 2
    while f"{name}-{counter}" in used:
        counter += 1
    resolved = f"{name}-{counter}"
    used.add(resolved)
    return resolved


def _format_single_node(
    node: ContentNode,
    fmt: str,
    child_paths: list[tuple[str, str, Path]],
) -> str:
    """Format one node's content (without recursing into children).

    Args:
        node: The content node to format.
        fmt: Output format ("markdown", "json", or "tree").
        child_paths: List of (title, content_type, relative_path) for each child.
    """
    if fmt == "json":
        data: dict[str, object] = {
            "url": node.url,
            "title": node.title,
            "content_type": node.content_type.value,
            "content": node.content,
            "metadata": node.metadata,
            "depth": node.depth,
            "error": node.error,
        }
        if child_paths:
            data["linked_content"] = [
                {
                    "title": title,
                    "content_type": ct,
                    "file": str(rel),
                }
                for title, ct, rel in child_paths
            ]
        return json.dumps(data, indent=2, ensure_ascii=False)

    if fmt == "tree":
        lines = []
        status = "\u2713" if node.content else "\u2717"
        content_preview = (
            node.content[:60].replace("\n", " ") + "..."
            if node.content and len(node.content) > 60
            else node.content.replace("\n", " ")
            if node.content
            else "[empty]"
        )
        lines.append(f"[{status}] {node.content_type.value}: {node.title or node.url}")
        lines.append(f"    URL: {node.url}")
        lines.append(f"    Content: {content_preview}")
        if node.error:
            lines.append(f"    Error: {node.error}")
        if child_paths:
            lines.append("")
            lines.append("Linked Content:")
            for title, ct, rel in child_paths:
                lines.append(f"  - [{ct}] {title} -> {rel}")
        return "\n".join(lines)

    # Default: markdown
    parts = []
    if node.title:
        parts.append(f"# {node.title}")
    parts.append(f"**Source:** {node.url}  ")
    parts.append(f"**Type:** {node.content_type.value}  ")

    if node.error:
        parts.append(f"**Error:** {node.error}  ")

    if node.content:
        parts.append("")
        parts.append(node.content)

    if child_paths:
        parts.append("")
        parts.append("## Linked Content")
        parts.append("")
        for title, ct, rel in child_paths:
            parts.append(f"- [{title}]({rel}) -- {ct}")

    return "\n".join(parts)


def _build_index_md(root: ContentNode, root_dir: Path, file_map: dict[int, Path]) -> str:
    """Build a human-readable INDEX.md with a nested tree of links."""
    lines = [
        "# Content Index",
        "",
        f"Extracted from: {root.url}",
        f"Total nodes: {root.total_nodes}",
        "",
        "## Content Tree",
        "",
    ]

    def _walk(node: ContentNode, depth: int) -> None:
        indent = "  " * depth
        rel = file_map.get(id(node), Path("content.md"))
        title = node.title or node.url
        ct = node.content_type.value
        lines.append(f"{indent}- [{title}](./{rel}) -- {ct}")
        for child in node.children:
            _walk(child, depth + 1)

    _walk(root, 0)
    return "\n".join(lines) + "\n"


def _build_index_json(
    root: ContentNode,
    root_dir: Path,
    file_map: dict[int, Path],
    fmt: str,
) -> str:
    """Build a machine-readable index.json."""

    def _walk(node: ContentNode) -> dict[str, object]:
        rel = file_map.get(id(node), Path("content.md"))
        entry: dict[str, object] = {
            "url": node.url,
            "title": node.title,
            "content_type": node.content_type.value,
            "file": str(rel),
            "children": [_walk(child) for child in node.children],
        }
        return entry

    data = {
        "source_url": root.url,
        "total_nodes": root.total_nodes,
        "generated_at": datetime.now(UTC).isoformat(),
        "format": fmt,
        "tree": _walk(root),
    }
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def write_tree_to_directory(root: ContentNode, output_dir: Path, fmt: str = "markdown") -> Path:
    """Write a ContentNode tree to a directory structure.

    Each node gets its own subdirectory (except root which uses output_dir directly).
    Index files (INDEX.md, index.json) are generated at the root.

    Args:
        root: The root ContentNode of the extraction tree.
        output_dir: Target directory (will be created if needed).
        fmt: Output format ("markdown", "json", or "tree").

    Returns:
        The output directory path.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    ext = FORMAT_EXTENSIONS.get(fmt, ".md")

    # Map node id -> relative file path (from output_dir)
    file_map: dict[int, Path] = {}

    def _write_node(node: ContentNode, node_dir: Path, rel_prefix: Path) -> None:
        """Recursively write a node and its children.

        Args:
            node: The node to write.
            node_dir: Absolute directory for this node's content file.
            rel_prefix: Relative path prefix from output_dir to node_dir.
        """
        node_dir.mkdir(parents=True, exist_ok=True)

        # Process children first to collect their paths for "Linked Content" links
        used_names: set[str] = set()
        child_paths: list[tuple[str, str, Path]] = []

        for child in node.children:
            raw_name = sanitize_filename(child.title or child.url)
            dir_name = _resolve_collision(raw_name, used_names)
            child_dir = node_dir / dir_name
            child_rel = rel_prefix / dir_name

            _write_node(child, child_dir, child_rel)

            # Relative path from this node's content file to child's content file
            child_file_rel = Path(dir_name) / f"content{ext}"
            child_paths.append((
                child.title or child.url,
                child.content_type.value,
                child_file_rel,
            ))

        # Write this node's content file
        content_file = node_dir / f"content{ext}"
        content = _format_single_node(node, fmt, child_paths)
        content_file.write_text(content, encoding="utf-8")

        # Record in file_map for index generation
        file_map[id(node)] = rel_prefix / f"content{ext}"

    _write_node(root, output_dir, Path(""))

    # Generate index files
    index_md = _build_index_md(root, output_dir, file_map)
    (output_dir / "INDEX.md").write_text(index_md, encoding="utf-8")

    index_json = _build_index_json(root, output_dir, file_map, fmt)
    (output_dir / "index.json").write_text(index_json, encoding="utf-8")

    return output_dir
