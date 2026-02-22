"""Custom exception hierarchy for the recursive content extractor."""

from __future__ import annotations


class ExtractorError(Exception):
    """Base exception for all extractor errors."""


class ExtractionFailedError(ExtractorError):
    """Raised when content extraction fails for a URL."""

    def __init__(self, url: str, reason: str = ""):
        self.url = url
        self.reason = reason
        super().__init__(f"Extraction failed for {url}: {reason}" if reason else url)


class NetworkError(ExtractorError):
    """Raised when a network request fails."""

    def __init__(self, url: str, reason: str = ""):
        self.url = url
        self.reason = reason
        super().__init__(f"Network error for {url}: {reason}" if reason else url)


class BrowserRequiredError(ExtractorError):
    """Raised when browser rendering is required but not available."""

    def __init__(self, url: str):
        self.url = url
        super().__init__(f"Browser required for {url}. Install playwright and use --browser flag.")


class DependencyMissingError(ExtractorError):
    """Raised when an optional dependency is not installed."""

    def __init__(self, package: str, feature: str = ""):
        self.package = package
        self.feature = feature
        msg = f"Missing dependency: {package}"
        if feature:
            msg += f" (required for {feature})"
        msg += f". Install with: pip install {package}"
        super().__init__(msg)
