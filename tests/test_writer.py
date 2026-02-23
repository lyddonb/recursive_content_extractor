"""Tests for the directory-based output writer."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from recursive_content_extractor.models import ContentNode, ContentType
from recursive_content_extractor.writer import (
    _resolve_collision,
    sanitize_filename,
    write_tree_to_directory,
)


class TestSanitizeFilename:
    def test_simple_title(self):
        assert sanitize_filename("My Article Title") == "my-article-title"

    def test_special_characters(self):
        assert sanitize_filename("Hello, World! (2024)") == "hello-world-2024"

    def test_url_input(self):
        result = sanitize_filename("https://example.com/path/to/page")
        assert result == "path-to-page"

    def test_url_with_no_path(self):
        result = sanitize_filename("https://example.com")
        assert result == "examplecom"

    def test_url_with_only_root(self):
        result = sanitize_filename("https://example.com/")
        assert result == "examplecom"

    def test_empty_string(self):
        assert sanitize_filename("") == "untitled"

    def test_whitespace_only(self):
        assert sanitize_filename("   ") == "untitled"

    def test_all_special_chars(self):
        assert sanitize_filename("!!!@@@###") == "untitled"

    def test_truncation(self):
        long_name = "a" * 100
        result = sanitize_filename(long_name, max_length=80)
        assert len(result) == 80

    def test_custom_max_length(self):
        result = sanitize_filename("some-long-title-here", max_length=10)
        assert len(result) <= 10

    def test_consecutive_hyphens_collapsed(self):
        assert sanitize_filename("foo---bar") == "foo-bar"

    def test_leading_trailing_hyphens_stripped(self):
        assert sanitize_filename("-foo-bar-") == "foo-bar"

    def test_unicode_stripped(self):
        result = sanitize_filename("caf\u00e9 r\u00e9sum\u00e9")
        assert result == "caf-rsum"

    def test_underscores_preserved(self):
        assert sanitize_filename("my_file_name") == "my_file_name"

    def test_truncation_strips_trailing_hyphen(self):
        result = sanitize_filename("abcde-fghij", max_length=6)
        assert result == "abcde"


class TestResolveCollision:
    def test_no_collision(self):
        used: set[str] = set()
        assert _resolve_collision("foo", used) == "foo"
        assert "foo" in used

    def test_first_collision(self):
        used = {"foo"}
        assert _resolve_collision("foo", used) == "foo-2"
        assert "foo-2" in used

    def test_multiple_collisions(self):
        used = {"foo", "foo-2", "foo-3"}
        assert _resolve_collision("foo", used) == "foo-4"

    def test_tracks_in_used_set(self):
        used: set[str] = set()
        _resolve_collision("bar", used)
        _resolve_collision("bar", used)
        _resolve_collision("bar", used)
        assert used == {"bar", "bar-2", "bar-3"}


class TestWriteTreeToDirectory:
    @pytest.fixture
    def simple_tree(self) -> ContentNode:
        return ContentNode(
            url="https://example.com/article",
            title="Root Article",
            content="Root content here.",
            content_type=ContentType.ARTICLE,
            depth=0,
        )

    @pytest.fixture
    def nested_tree(self) -> ContentNode:
        grandchild = ContentNode(
            url="https://example.com/linked-page",
            title="Linked Page",
            content="Linked page content.",
            content_type=ContentType.ARTICLE,
            depth=2,
        )
        tweet = ContentNode(
            url="https://x.com/user/status/123",
            title="Tweet by @user",
            content="Tweet text here.",
            content_type=ContentType.X_POST,
            depth=1,
            children=[grandchild],
        )
        video = ContentNode(
            url="https://youtube.com/watch?v=abc",
            title="Video Title",
            content="Transcript here.",
            content_type=ContentType.YOUTUBE,
            depth=1,
        )
        article = ContentNode(
            url="https://example.com/some-article",
            title="Some Article",
            content="Article content.",
            content_type=ContentType.ARTICLE,
            depth=1,
        )
        return ContentNode(
            url="https://example.com/root",
            title="Root Page",
            content="Root content.",
            content_type=ContentType.ARTICLE,
            depth=0,
            children=[tweet, video, article],
        )

    def test_single_node_creates_files(self, tmp_path: Path, simple_tree: ContentNode):
        out = tmp_path / "output"
        write_tree_to_directory(simple_tree, out, "markdown")

        assert (out / "content.md").exists()
        assert (out / "INDEX.md").exists()
        assert (out / "index.json").exists()

    def test_single_node_content_md(self, tmp_path: Path, simple_tree: ContentNode):
        out = tmp_path / "output"
        write_tree_to_directory(simple_tree, out, "markdown")

        content = (out / "content.md").read_text()
        assert "# Root Article" in content
        assert "Root content here." in content
        assert "https://example.com/article" in content

    def test_nested_tree_structure(self, tmp_path: Path, nested_tree: ContentNode):
        out = tmp_path / "output"
        write_tree_to_directory(nested_tree, out, "markdown")

        assert (out / "content.md").exists()
        assert (out / "tweet-by-user" / "content.md").exists()
        assert (out / "tweet-by-user" / "linked-page" / "content.md").exists()
        assert (out / "video-title" / "content.md").exists()
        assert (out / "some-article" / "content.md").exists()

    def test_root_content_has_linked_content_section(
        self, tmp_path: Path, nested_tree: ContentNode
    ):
        out = tmp_path / "output"
        write_tree_to_directory(nested_tree, out, "markdown")

        root_content = (out / "content.md").read_text()
        assert "## Linked Content" in root_content
        assert "tweet-by-user/content.md" in root_content
        assert "video-title/content.md" in root_content
        assert "some-article/content.md" in root_content

    def test_index_md_content(self, tmp_path: Path, nested_tree: ContentNode):
        out = tmp_path / "output"
        write_tree_to_directory(nested_tree, out, "markdown")

        index = (out / "INDEX.md").read_text()
        assert "# Content Index" in index
        assert "https://example.com/root" in index
        assert "Total nodes: 5" in index
        assert "[Root Page]" in index
        assert "[Tweet by @user]" in index
        assert "[Linked Page]" in index
        assert "[Video Title]" in index

    def test_index_json_valid(self, tmp_path: Path, nested_tree: ContentNode):
        out = tmp_path / "output"
        write_tree_to_directory(nested_tree, out, "markdown")

        data = json.loads((out / "index.json").read_text())
        assert data["source_url"] == "https://example.com/root"
        assert data["total_nodes"] == 5
        assert data["format"] == "markdown"
        assert "generated_at" in data
        assert data["tree"]["title"] == "Root Page"
        assert len(data["tree"]["children"]) == 3

    def test_json_format(self, tmp_path: Path, simple_tree: ContentNode):
        out = tmp_path / "output"
        write_tree_to_directory(simple_tree, out, "json")

        content_file = out / "content.json"
        assert content_file.exists()
        data = json.loads(content_file.read_text())
        assert data["url"] == "https://example.com/article"
        assert data["title"] == "Root Article"
        assert data["content"] == "Root content here."

    def test_tree_format(self, tmp_path: Path, simple_tree: ContentNode):
        out = tmp_path / "output"
        write_tree_to_directory(simple_tree, out, "tree")

        content_file = out / "content.txt"
        assert content_file.exists()
        content = content_file.read_text()
        assert "article" in content
        assert "Root Article" in content

    def test_collision_handling(self, tmp_path: Path):
        child1 = ContentNode(
            url="https://example.com/a",
            title="Same Title",
            content="Content A",
            content_type=ContentType.ARTICLE,
            depth=1,
        )
        child2 = ContentNode(
            url="https://example.com/b",
            title="Same Title",
            content="Content B",
            content_type=ContentType.ARTICLE,
            depth=1,
        )
        root = ContentNode(
            url="https://example.com/root",
            title="Root",
            content="Root content",
            content_type=ContentType.ARTICLE,
            children=[child1, child2],
        )
        out = tmp_path / "output"
        write_tree_to_directory(root, out, "markdown")

        assert (out / "same-title" / "content.md").exists()
        assert (out / "same-title-2" / "content.md").exists()

    def test_returns_output_dir(self, tmp_path: Path, simple_tree: ContentNode):
        out = tmp_path / "output"
        result = write_tree_to_directory(simple_tree, out, "markdown")
        assert result == out

    def test_creates_output_dir_if_missing(self, tmp_path: Path, simple_tree: ContentNode):
        out = tmp_path / "deep" / "nested" / "output"
        assert not out.exists()
        write_tree_to_directory(simple_tree, out, "markdown")
        assert out.exists()

    def test_node_with_error(self, tmp_path: Path):
        node = ContentNode(
            url="https://example.com/fail",
            title="Failed Page",
            content="",
            content_type=ContentType.ERROR,
            error="Connection timed out",
        )
        out = tmp_path / "output"
        write_tree_to_directory(node, out, "markdown")

        content = (out / "content.md").read_text()
        assert "Connection timed out" in content

    def test_index_json_child_files_are_relative(
        self, tmp_path: Path, nested_tree: ContentNode
    ):
        out = tmp_path / "output"
        write_tree_to_directory(nested_tree, out, "markdown")

        data = json.loads((out / "index.json").read_text())
        tree = data["tree"]
        # Root file should be relative (no leading /)
        assert not tree["file"].startswith("/")
        # Check a nested child
        tweet = tree["children"][0]
        assert "tweet-by-user" in tweet["file"]
        linked = tweet["children"][0]
        assert "linked-page" in linked["file"]
