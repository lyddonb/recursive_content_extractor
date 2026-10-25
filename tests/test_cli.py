"""Tests for the rce command-line entry point."""

from __future__ import annotations

import json

import httpx
from click.testing import CliRunner

from recursive_content_extractor.cli import main

PAGE = "<html><head><title>Root</title></head><body><p>Root page.</p><a href='/missing'>x</a></body></html>"


def run(args: list[str]) -> tuple[int, dict]:
    with CliRunner().isolated_filesystem():
        result = CliRunner().invoke(
            main, [*args, "-q", "--retries", "0", "--delay", "0", "-f", "json", "-o", "out.json"]
        )
        with open("out.json") as f:
            return result.exit_code, json.load(f)


def test_exits_1_and_still_writes_output_when_root_fails(httpx_mock):
    httpx_mock.add_exception(httpx.ConnectError("connection refused"), url="https://example.com/")

    code, tree = run(["https://example.com/", "-d", "0"])

    assert code == 1
    assert tree["content_type"] == "error"
    assert tree["error"] == "connection refused"


def test_exits_0_when_only_a_child_fails(httpx_mock):
    httpx_mock.add_response(url="https://example.com/", text=PAGE)
    httpx_mock.add_response(url="https://example.com/missing", status_code=404)

    code, tree = run(["https://example.com/", "-d", "1"])

    assert code == 0
    assert tree["content_type"] == "article"
    assert [c["content_type"] for c in tree["children"]] == ["error"]
