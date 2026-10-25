"""GitHub repository extractor.

Uses the GitHub REST API for structured metadata and README content,
with a raw.githubusercontent.com fallback when rate-limited.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

from recursive_content_extractor.extractors.base import BaseExtractor
from recursive_content_extractor.models import ContentType, ExtractionResult

logger = logging.getLogger(__name__)

# Matches github.com/{owner}/{repo} with optional trailing path
_REPO_PATTERN = re.compile(
    r"^https?://(?:www\.)?github\.com/"
    r"(?P<owner>[A-Za-z0-9\-_.]+)/"
    r"(?P<repo>[A-Za-z0-9\-_.]+)"
    r"(?:/(?P<rest>.*))?$"
)

# GitHub paths that are NOT repositories
_RESERVED_PATHS = frozenset(
    {
        "explore",
        "topics",
        "trending",
        "collections",
        "events",
        "sponsors",
        "settings",
        "login",
        "signup",
        "join",
        "pricing",
        "features",
        "marketplace",
        "notifications",
        "new",
        "organizations",
        "codespaces",
        "issues",
        "pulls",
        "discussions",
        "search",
        "about",
        "security",
        "enterprise",
        "team",
        "customer-stories",
        "readme",
        "apps",
        "site",
        "user-attachments",
        "assets",
    }
)

# Badge/shield hosts to skip when extracting links from README
_BADGE_HOSTS = frozenset(
    {
        "img.shields.io",
        "badge.fury.io",
        "badges.gitter.im",
        "travis-ci.org",
        "travis-ci.com",
        "ci.appveyor.com",
        "codecov.io",
        "coveralls.io",
        "david-dm.org",
        "snyk.io",
        "github.com/workflows",
    }
)

_URL_PATTERN = re.compile(r"https?://[^\s)\]>\"'`]+")


class GitHubExtractor(BaseExtractor):
    """Extracts content from GitHub repositories via the REST API.

    Strategy order:
    1. GitHub REST API (metadata + README)
    2. Raw README fallback (no rate limits, loses metadata)
    """

    @staticmethod
    def can_handle(url: str) -> bool:
        parsed = urlparse(url)
        domain = parsed.netloc.lower().removeprefix("www.")
        if domain != "github.com":
            return False
        match = _REPO_PATTERN.match(url)
        if not match:
            return False
        owner = match.group("owner")
        return owner.lower() not in _RESERVED_PATHS

    @staticmethod
    def priority() -> int:
        return 45

    async def extract(self, url: str) -> ExtractionResult:
        match = _REPO_PATTERN.match(url)
        if not match:
            return ExtractionResult(
                url=url,
                content_type=ContentType.ERROR,
                content="[Could not parse GitHub URL]",
            )

        owner = match.group("owner")
        repo = match.group("repo").removesuffix(".git")
        rest = match.group("rest") or ""

        # Detect blob URLs: /blob/{ref}/{path}
        blob_match = re.match(r"blob/([^/]+)/(.+)", rest)
        if blob_match:
            ref = blob_match.group(1)
            path = blob_match.group(2)
            return await self._extract_blob(url, owner, repo, ref, path)

        # Strategy 1: GitHub REST API
        result = await self._try_api(url, owner, repo)
        if result and result.content:
            return result

        # Strategy 2: Raw README fallback
        result = await self._try_raw_readme(url, owner, repo)
        if result and result.content:
            return result

        # All strategies failed
        logger.warning(f"All extraction strategies failed for {url}")
        return ExtractionResult(
            url=url,
            title=f"{owner}/{repo}",
            content=f"[Could not extract content from {url}]",
            content_type=ContentType.GITHUB,
            metadata={"owner": owner, "repo": repo},
        )

    async def _try_api(self, original_url: str, owner: str, repo: str) -> ExtractionResult | None:
        """Use GitHub REST API for metadata and README."""
        client = await self._get_client()

        try:
            # Fetch repo metadata
            api_url = f"https://api.github.com/repos/{owner}/{repo}"
            resp = await client.get(
                api_url,
                headers={"Accept": "application/vnd.github+json"},
            )
            if resp.status_code != 200:
                logger.debug(f"GitHub API returned {resp.status_code} for {api_url}")
                return None

            repo_data = resp.json()

            # Fetch README
            readme_url = f"https://api.github.com/repos/{owner}/{repo}/readme"
            readme_resp = await client.get(
                readme_url,
                headers={"Accept": "application/vnd.github.raw+json"},
            )
            readme_content = ""
            if readme_resp.status_code == 200:
                readme_content = readme_resp.text

            # Build formatted content
            parts: list[str] = []
            parts.append(f"# {owner}/{repo}")

            description = repo_data.get("description", "")
            if description:
                parts.append(description)

            # Stats line
            stats: list[str] = []
            language = repo_data.get("language")
            if language:
                stats.append(f"**Language:** {language}")
            stars = repo_data.get("stargazers_count", 0)
            stats.append(f"**Stars:** {stars:,}")
            forks = repo_data.get("forks_count", 0)
            stats.append(f"**Forks:** {forks:,}")
            license_info = repo_data.get("license")
            if license_info and license_info.get("spdx_id"):
                stats.append(f"**License:** {license_info['spdx_id']}")
            if stats:
                parts.append(" | ".join(stats))

            topics = repo_data.get("topics", [])
            if topics:
                parts.append(f"**Topics:** {', '.join(topics)}")

            if readme_content:
                parts.append("\n---\n")
                parts.append(readme_content)

            content = "\n\n".join(parts)

            # Extract links
            links: list[str] = []
            homepage = repo_data.get("homepage")
            if homepage and homepage.startswith("http"):
                links.append(homepage)
            if readme_content:
                links.extend(self._extract_readme_links(readme_content, owner, repo))

            return ExtractionResult(
                url=original_url,
                title=f"{owner}/{repo}" + (f" - {description}" if description else ""),
                content=content[: self.config.max_content_length],
                content_type=ContentType.GITHUB,
                links=links,
                metadata={
                    "owner": owner,
                    "repo": repo,
                    "stars": stars,
                    "forks": forks,
                    "language": language,
                    "topics": topics,
                    "license": license_info.get("spdx_id") if license_info else None,
                    "homepage": homepage,
                    "source": "github_api",
                },
            )
        except Exception as e:
            logger.debug(f"GitHub API extraction failed: {e}")
            return None

    async def _try_raw_readme(
        self, original_url: str, owner: str, repo: str
    ) -> ExtractionResult | None:
        """Fetch README directly from raw.githubusercontent.com."""
        client = await self._get_client()

        for branch in ("main", "master"):
            try:
                raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/README.md"
                resp = await client.get(raw_url)
                if resp.status_code == 200:
                    readme = resp.text
                    links = self._extract_readme_links(readme, owner, repo)

                    return ExtractionResult(
                        url=original_url,
                        title=f"{owner}/{repo}",
                        content=f"# {owner}/{repo}\n\n{readme}"[: self.config.max_content_length],
                        content_type=ContentType.GITHUB,
                        links=links,
                        metadata={
                            "owner": owner,
                            "repo": repo,
                            "source": "raw_readme",
                        },
                    )
            except Exception as e:
                logger.debug(f"Raw README fetch failed ({branch}): {e}")

        return None

    async def _extract_blob(
        self, original_url: str, owner: str, repo: str, ref: str, path: str
    ) -> ExtractionResult:
        """Extract a specific file from a repo via the contents API."""
        client = await self._get_client()

        try:
            api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={ref}"
            resp = await client.get(
                api_url,
                headers={"Accept": "application/vnd.github.raw+json"},
            )
            if resp.status_code == 200:
                return ExtractionResult(
                    url=original_url,
                    title=f"{owner}/{repo}/{path}",
                    content=resp.text[: self.config.max_content_length],
                    content_type=ContentType.GITHUB,
                    metadata={
                        "owner": owner,
                        "repo": repo,
                        "ref": ref,
                        "path": path,
                        "source": "github_api",
                    },
                )
        except Exception as e:
            logger.debug(f"Blob extraction failed: {e}")

        return ExtractionResult(
            url=original_url,
            title=f"{owner}/{repo}/{path}",
            content=f"[Could not extract file content from {original_url}]",
            content_type=ContentType.GITHUB,
            metadata={"owner": owner, "repo": repo, "ref": ref, "path": path},
        )

    @staticmethod
    def _extract_readme_links(readme: str, owner: str, repo: str) -> list[str]:
        """Extract HTTP links from README, skipping badges and self-references."""
        found: list[str] = []
        seen: set[str] = set()

        for match in _URL_PATTERN.finditer(readme):
            url = match.group(0).rstrip(".,;:!?)>\"'`")
            if url in seen:
                continue
            seen.add(url)

            parsed = urlparse(url)
            host = parsed.netloc.lower()

            # Skip badges/CI links
            if any(badge in host for badge in _BADGE_HOSTS):
                continue

            # Skip self-referencing links
            if host in ("github.com", "www.github.com"):
                path = parsed.path.strip("/")
                if path.startswith(f"{owner}/{repo}"):
                    continue

            found.append(url)

        return found
