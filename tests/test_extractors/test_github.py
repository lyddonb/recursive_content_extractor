"""Tests for the GitHub extractor."""

from __future__ import annotations

import pytest

from recursive_content_extractor.extractors.github import GitHubExtractor
from recursive_content_extractor.models import ContentType, ExtractorConfig


class TestGitHubCanHandle:
    def test_handles_repo_url(self):
        assert GitHubExtractor.can_handle("https://github.com/owner/repo") is True

    def test_handles_repo_with_path(self):
        assert GitHubExtractor.can_handle("https://github.com/owner/repo/tree/main") is True

    def test_handles_blob_url(self):
        assert (
            GitHubExtractor.can_handle("https://github.com/owner/repo/blob/main/README.md") is True
        )

    def test_handles_www_prefix(self):
        assert GitHubExtractor.can_handle("https://www.github.com/owner/repo") is True

    def test_rejects_non_github(self):
        assert GitHubExtractor.can_handle("https://example.com/owner/repo") is False
        assert GitHubExtractor.can_handle("https://notgithub.com/owner/repo") is False

    def test_rejects_reserved_paths(self):
        assert GitHubExtractor.can_handle("https://github.com/explore") is False
        assert GitHubExtractor.can_handle("https://github.com/settings/profile") is False
        assert GitHubExtractor.can_handle("https://github.com/login") is False
        assert GitHubExtractor.can_handle("https://github.com/signup") is False
        assert GitHubExtractor.can_handle("https://github.com/trending") is False
        assert GitHubExtractor.can_handle("https://github.com/topics/python") is False

    def test_rejects_asset_urls(self):
        assert (
            GitHubExtractor.can_handle(
                "https://github.com/user-attachments/assets/f79aaf03-fd2d-4c71-a630-7027adeb9bfe"
            )
            is False
        )

    def test_rejects_bare_github(self):
        assert GitHubExtractor.can_handle("https://github.com") is False
        assert GitHubExtractor.can_handle("https://github.com/") is False

    def test_handles_dotted_names(self):
        assert GitHubExtractor.can_handle("https://github.com/org.name/repo.js") is True

    def test_handles_hyphenated_names(self):
        assert GitHubExtractor.can_handle("https://github.com/my-org/my-repo") is True

    def test_priority(self):
        assert GitHubExtractor.priority() == 45


class TestGitHubExtract:
    @pytest.mark.asyncio
    async def test_api_success(self, httpx_mock, github_repo_response):
        httpx_mock.add_response(
            url="https://api.github.com/repos/testowner/test-repo",
            json=github_repo_response,
        )
        httpx_mock.add_response(
            url="https://api.github.com/repos/testowner/test-repo/readme",
            text="# Test Repo\n\nThis is the README content.",
        )

        extractor = GitHubExtractor(config=ExtractorConfig(timeout=10))
        result = await extractor.extract("https://github.com/testowner/test-repo")

        assert result.content_type == ContentType.GITHUB
        assert "testowner/test-repo" in result.title
        assert "A test repository" in result.content
        assert "1,234" in result.content  # Stars formatted
        assert "Python" in result.content
        assert result.metadata["source"] == "github_api"
        assert result.metadata["stars"] == 1234
        await extractor.close()

    @pytest.mark.asyncio
    async def test_missing_readme(self, httpx_mock, github_repo_response):
        httpx_mock.add_response(
            url="https://api.github.com/repos/testowner/test-repo",
            json=github_repo_response,
        )
        httpx_mock.add_response(
            url="https://api.github.com/repos/testowner/test-repo/readme",
            status_code=404,
        )

        extractor = GitHubExtractor(config=ExtractorConfig(timeout=10))
        result = await extractor.extract("https://github.com/testowner/test-repo")

        assert result.content_type == ContentType.GITHUB
        assert "testowner/test-repo" in result.content
        assert result.metadata["source"] == "github_api"
        await extractor.close()

    @pytest.mark.asyncio
    async def test_rate_limited_falls_back_to_raw(self, httpx_mock):
        # API rate limited
        httpx_mock.add_response(
            url="https://api.github.com/repos/testowner/test-repo",
            status_code=403,
        )
        # Raw README succeeds
        httpx_mock.add_response(
            url="https://raw.githubusercontent.com/testowner/test-repo/main/README.md",
            text="# Test Repo\n\nFallback README content.",
        )

        extractor = GitHubExtractor(config=ExtractorConfig(timeout=10))
        result = await extractor.extract("https://github.com/testowner/test-repo")

        assert result.content_type == ContentType.GITHUB
        assert "Fallback README content" in result.content
        assert result.metadata["source"] == "raw_readme"
        await extractor.close()

    @pytest.mark.asyncio
    async def test_blob_url_extraction(self, httpx_mock):
        httpx_mock.add_response(
            url="https://api.github.com/repos/owner/repo/contents/src/main.py?ref=main",
            text='print("hello world")',
        )

        extractor = GitHubExtractor(config=ExtractorConfig(timeout=10))
        result = await extractor.extract("https://github.com/owner/repo/blob/main/src/main.py")

        assert result.content_type == ContentType.GITHUB
        assert 'print("hello world")' in result.content
        assert result.metadata["path"] == "src/main.py"
        assert result.metadata["ref"] == "main"
        await extractor.close()

    @pytest.mark.asyncio
    async def test_all_strategies_fail(self, httpx_mock):
        httpx_mock.add_response(
            url="https://api.github.com/repos/testowner/test-repo",
            status_code=500,
        )
        httpx_mock.add_response(
            url="https://raw.githubusercontent.com/testowner/test-repo/main/README.md",
            status_code=404,
        )
        httpx_mock.add_response(
            url="https://raw.githubusercontent.com/testowner/test-repo/master/README.md",
            status_code=404,
        )

        extractor = GitHubExtractor(config=ExtractorConfig(timeout=10, max_retries=0))
        result = await extractor.extract("https://github.com/testowner/test-repo")

        assert "Could not extract" in result.content
        assert result.content_type == ContentType.GITHUB
        await extractor.close()

    @pytest.mark.asyncio
    async def test_homepage_in_links(self, httpx_mock, github_repo_response):
        httpx_mock.add_response(
            url="https://api.github.com/repos/testowner/test-repo",
            json=github_repo_response,
        )
        httpx_mock.add_response(
            url="https://api.github.com/repos/testowner/test-repo/readme",
            text="# Test\n\nNo external links here.",
        )

        extractor = GitHubExtractor(config=ExtractorConfig(timeout=10))
        result = await extractor.extract("https://github.com/testowner/test-repo")

        assert "https://test-repo.example.com" in result.links
        await extractor.close()

    @pytest.mark.asyncio
    async def test_max_content_length_respected(self, httpx_mock, github_repo_response):
        httpx_mock.add_response(
            url="https://api.github.com/repos/testowner/test-repo",
            json=github_repo_response,
        )
        httpx_mock.add_response(
            url="https://api.github.com/repos/testowner/test-repo/readme",
            text="x" * 100_000,
        )

        config = ExtractorConfig(timeout=10, max_content_length=500)
        extractor = GitHubExtractor(config=config)
        result = await extractor.extract("https://github.com/testowner/test-repo")

        assert len(result.content) <= 500
        await extractor.close()

    @pytest.mark.asyncio
    async def test_git_suffix_stripped(self, httpx_mock, github_repo_response):
        httpx_mock.add_response(
            url="https://api.github.com/repos/testowner/test-repo",
            json=github_repo_response,
        )
        httpx_mock.add_response(
            url="https://api.github.com/repos/testowner/test-repo/readme",
            text="# Test",
        )

        extractor = GitHubExtractor(config=ExtractorConfig(timeout=10))
        result = await extractor.extract("https://github.com/testowner/test-repo.git")

        assert result.content_type == ContentType.GITHUB
        assert result.metadata["repo"] == "test-repo"
        await extractor.close()
