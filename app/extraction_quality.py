"""Extraction-quality validation for the Agri-AI Adviser.

This module assesses the quality of PDF text extraction and provides a
deterministic gate to prevent poor extractions (e.g., empty pages from
scanned/image PDFs) from being converted into knowledge Markdown.

This module is strictly additive. It does not modify any existing module.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.pdf_extractor import PdfExtractionResult


@dataclass
class ExtractionQualityReport:
    """Quality assessment of a PDF text extraction."""

    page_count: int = 0
    empty_pages: int = 0
    total_chars: int = 0
    issues: list[str] = field(default_factory=list)

    @property
    def is_acceptable(self) -> bool:
        return not self.issues


def assess_extraction_quality(extraction: PdfExtractionResult) -> ExtractionQualityReport:
    """Assess the quality of a PDF text extraction.

    Returns an ``ExtractionQualityReport``. The report is acceptable only when
    there are no issues (e.g., no empty pages, no extraction errors).
    """
    report = ExtractionQualityReport(page_count=extraction.page_count)

    for page in extraction.pages:
        text = (page.text or "").strip()
        report.total_chars += len(text)
        if not text:
            report.empty_pages += 1

    if extraction.page_count == 0:
        report.issues.append("No pages extracted from the PDF.")

    if report.empty_pages > 0:
        report.issues.append(f"{report.empty_pages} page(s) contained no extractable text.")

    if report.total_chars == 0:
        report.issues.append("No text was extracted from the PDF (possibly a scanned/image PDF).")

    for error in extraction.errors:
        report.issues.append(error)

    return report


def validate_extraction(extraction: PdfExtractionResult) -> tuple[bool, ExtractionQualityReport]:
    """Validate a PDF extraction and return ``(is_acceptable, report)``."""
    report = assess_extraction_quality(extraction)
    return report.is_acceptable, report