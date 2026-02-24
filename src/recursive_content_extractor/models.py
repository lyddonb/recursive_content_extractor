"""Data models for the recursive content extractor."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class ContentType(StrEnum):
    """Types of content the extractor can handle."""

    ARTICLE = "article"
    X_THREAD = "x_thread"
    X_POST = "x_post"
    YOUTUBE = "youtube"
    PDF = "pdf"
    GITHUB = "github"
    ARXIV = "arxiv"
    GENERIC = "generic"
    UNKNOWN = "unknown"
    ERROR = "error"


@dataclass
class ExtractionResult:
    """Result from a single extractor."""

    url: str
    title: str = ""
    content: str = ""
    content_type: ContentType = ContentType.UNKNOWN
    links: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    raw_html: str = ""
    extracted_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def __repr__(self) -> str:
        return (
            f"ExtractionResult(url='{self.url}', "
            f"type={self.content_type.value}, "
            f"content_len={len(self.content)}, "
            f"links={len(self.links)})"
        )


@dataclass
class ContentNode:
    """A node in the recursive content tree."""

    url: str
    title: str = ""
    content: str = ""
    content_type: ContentType = ContentType.UNKNOWN
    metadata: dict[str, Any] = field(default_factory=dict)
    children: list[ContentNode] = field(default_factory=list)
    depth: int = 0
    error: str | None = None

    def to_dict(self) -> dict:
        """Convert to a serializable dictionary."""
        return {
            "url": self.url,
            "title": self.title,
            "content_type": self.content_type.value,
            "content": self.content,
            "metadata": self.metadata,
            "depth": self.depth,
            "error": self.error,
            "children": [child.to_dict() for child in self.children],
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def to_markdown(self, _level: int = 0) -> str:
        """Flatten the tree into a single markdown document."""
        parts = []
        prefix = "#" * min(_level + 1, 6)

        if self.title:
            parts.append(f"{prefix} {self.title}")
        parts.append(f"**Source:** {self.url}  ")
        parts.append(f"**Type:** {self.content_type.value}  ")

        if self.error:
            parts.append(f"**Error:** {self.error}  ")

        if self.content:
            parts.append("")
            parts.append(self.content)

        if self.children:
            parts.append("")
            parts.append(f"{prefix}# Linked Content")
            for child in self.children:
                parts.append("")
                parts.append(child.to_markdown(_level + 1))

        return "\n".join(parts)

    def flatten(self) -> list[ContentNode]:
        """Return all nodes as a flat list (BFS order)."""
        result = [self]
        queue = list(self.children)
        while queue:
            node = queue.pop(0)
            result.append(node)
            queue.extend(node.children)
        return result

    @property
    def total_nodes(self) -> int:
        return len(self.flatten())

    @property
    def total_content_length(self) -> int:
        return sum(len(n.content) for n in self.flatten())


@dataclass
class ExtractorConfig:
    """Configuration for the recursive extractor."""

    depth: int = 1
    rate_limit_delay: float = 1.0
    max_links_per_page: int = 20
    timeout: int = 30
    use_browser: bool = False
    include_patterns: list[str] = field(default_factory=lambda: ["*"])
    exclude_patterns: list[str] = field(default_factory=list)
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
    max_content_length: int = 50_000
    follow_same_domain_only: bool = False
    extract_embedded_urls: bool = True
    max_concurrent_requests: int = 5
    max_retries: int = 2
    retry_backoff_factor: float = 0.5

    def __post_init__(self):
        if self.depth < 0:
            raise ValueError(f"depth must be >= 0, got {self.depth}")
        if self.timeout <= 0:
            raise ValueError(f"timeout must be > 0, got {self.timeout}")
        if self.max_links_per_page < 0:
            raise ValueError(f"max_links_per_page must be >= 0, got {self.max_links_per_page}")
        if self.max_concurrent_requests < 1:
            raise ValueError(
                f"max_concurrent_requests must be >= 1, got {self.max_concurrent_requests}"
            )
        if self.rate_limit_delay < 0:
            raise ValueError(f"rate_limit_delay must be >= 0, got {self.rate_limit_delay}")
        if self.max_retries < 0:
            raise ValueError(f"max_retries must be >= 0, got {self.max_retries}")
        if self.retry_backoff_factor < 0:
            raise ValueError(
                f"retry_backoff_factor must be >= 0, got {self.retry_backoff_factor}"
            )
