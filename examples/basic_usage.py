#!/usr/bin/env python3
"""Example usage of the Recursive Content Extractor.

Run: python -m examples.basic_usage
  or: python examples/basic_usage.py
"""

from __future__ import annotations

import asyncio
import json
import sys

from recursive_content_extractor import (
    BaseExtractor,
    ContentType,
    ExtractionResult,
    ExtractorConfig,
    RecursiveExtractor,
    extract_url,
)


async def example_basic():
    """Basic extraction with default settings."""
    print("=" * 60)
    print("Example 1: Basic extraction (depth=0)")
    print("=" * 60)

    result = await extract_url("https://example.com", depth=0)

    print(f"Title: {result.title}")
    print(f"Content length: {len(result.content)} chars")
    print(f"Children: {len(result.children)}")
    print(f"Content preview: {result.content[:200]}...")
    print()


async def example_twitter():
    """Extract an X/Twitter thread and follow embedded links."""
    print("=" * 60)
    print("Example 2: X/Twitter thread extraction")
    print("=" * 60)

    config = ExtractorConfig(depth=1, max_links_per_page=5, rate_limit_delay=1.0)
    extractor = RecursiveExtractor(config=config)
    result = await extractor.extract("https://x.com/karpathy/status/1886192184808149383")

    print(f"Root: {result.title}")
    print(f"Type: {result.content_type.value}")
    print(f"Content: {result.content[:300]}...")
    print(f"\nFound {len(result.children)} linked items:")
    for child in result.children:
        print(f"  - [{child.content_type.value}] {child.title or child.url}")
    print()


async def example_youtube():
    """Extract a YouTube video transcript."""
    print("=" * 60)
    print("Example 3: YouTube transcript extraction")
    print("=" * 60)

    result = await extract_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ", depth=0)

    print(f"Title: {result.title}")
    print(f"Type: {result.content_type.value}")
    print(f"Has transcript: {result.metadata.get('has_transcript', False)}")
    print(f"Content preview: {result.content[:300]}...")
    print()


async def example_custom_extractor():
    """Register and use a custom extractor."""
    print("=" * 60)
    print("Example 4: Custom extractor")
    print("=" * 60)

    class HackerNewsExtractor(BaseExtractor):
        @staticmethod
        def can_handle(url: str) -> bool:
            return "news.ycombinator.com" in url

        @staticmethod
        def priority() -> int:
            return 60

        async def extract(self, url: str) -> ExtractionResult:
            return ExtractionResult(
                url=url,
                title="HN Discussion",
                content="[Custom HN extraction would go here]",
                content_type=ContentType.ARTICLE,
                links=[],
                metadata={"source": "hackernews"},
            )

    extractor = RecursiveExtractor(depth=0)
    extractor.register_extractor(HackerNewsExtractor, priority=60)
    result = await extractor.extract("https://news.ycombinator.com/item?id=12345")

    print(f"Title: {result.title}")
    print(f"Content: {result.content}")
    print()


async def example_json_output():
    """Export results as JSON."""
    print("=" * 60)
    print("Example 5: JSON output")
    print("=" * 60)

    result = await extract_url("https://example.com", depth=0)
    data = result.to_dict()
    print(json.dumps(data, indent=2)[:500])
    print("...")
    print()


def _print_tree(node, indent=0):
    prefix = "  " * indent + ("\u251c\u2500\u2500 " if indent > 0 else "")
    icon = "\u2713" if node.content else "\u2717"
    label = node.title[:50] if node.title else node.url[:50]
    print(f"{prefix}[{icon}] {node.content_type.value}: {label}")
    for child in node.children:
        _print_tree(child, indent + 1)


async def main():
    """Run all examples."""
    examples = [
        ("Basic extraction", example_basic),
        ("JSON output", example_json_output),
    ]

    if "--all" in sys.argv:
        examples.extend(
            [
                ("Twitter extraction", example_twitter),
                ("YouTube extraction", example_youtube),
                ("Custom extractor", example_custom_extractor),
            ]
        )
    else:
        print("Run with --all to include network-dependent examples\n")

    for name, example_fn in examples:
        try:
            await example_fn()
        except Exception as e:
            print(f"Example '{name}' failed: {e}\n")


if __name__ == "__main__":
    asyncio.run(main())
