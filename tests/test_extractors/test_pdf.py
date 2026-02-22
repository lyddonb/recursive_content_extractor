"""Tests for the PDF extractor."""

from __future__ import annotations

from recursive_content_extractor.extractors.pdf import PDFExtractor


class TestPDFCanHandle:
    def test_handles_pdf_extension(self):
        assert PDFExtractor.can_handle("https://example.com/paper.pdf") is True

    def test_handles_pdf_with_query_params(self):
        assert PDFExtractor.can_handle("https://example.com/paper.pdf?dl=1") is True

    def test_handles_pdf_with_fragment(self):
        assert PDFExtractor.can_handle("https://example.com/paper.pdf#page=5") is True

    def test_handles_arxiv(self):
        assert PDFExtractor.can_handle("https://arxiv.org/pdf/2301.07041") is True

    def test_handles_ssrn(self):
        assert PDFExtractor.can_handle("https://papers.ssrn.com/abstract=1234") is True

    def test_handles_acm(self):
        assert PDFExtractor.can_handle("https://dl.acm.org/doi/pdf/10.1145/123") is True

    def test_rejects_non_pdf(self):
        assert PDFExtractor.can_handle("https://example.com/article") is False
        assert PDFExtractor.can_handle("https://example.com/paper.doc") is False

    def test_priority(self):
        assert PDFExtractor.priority() == 40
