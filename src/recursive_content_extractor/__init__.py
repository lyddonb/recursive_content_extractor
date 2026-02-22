"""Recursive Content Extractor -- extract content trees from web pages."""

from recursive_content_extractor.extractor import RecursiveExtractor, extract_url
from recursive_content_extractor.extractors.base import BaseExtractor
from recursive_content_extractor.models import (
    ContentNode,
    ContentType,
    ExtractionResult,
    ExtractorConfig,
)

__all__ = [
    "BaseExtractor",
    "ContentNode",
    "ContentType",
    "ExtractionResult",
    "ExtractorConfig",
    "RecursiveExtractor",
    "extract_url",
]
