"""PDF text extraction for the Agri-AI Adviser.

This module provides deterministic, verbatim text extraction from PDF files
using the ``pypdf`` library. It preserves page boundaries and does not
paraphrase, rewrite, or invent agricultural facts.

This module is strictly additive. It does not modify any existing module.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader


@dataclass
class PdfPage:
    """A single page of extracted text from a PDF."""

    page_number: int  # 1-based
    text: str


@dataclass
class PdfExtractionResult:
    """Result of extracting text from a PDF."""

    source_path: str
    pages: list[PdfPage] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def full_text(self) -> str:
        return "\n\n".join(page.text for page in self.pages)


def extract_pdf_text(pdf_path: str | Path) -> PdfExtractionResult:
    """Extract text from a PDF, preserving page boundaries.

    Returns a ``PdfExtractionResult`` with one ``PdfPage`` per PDF page.
    Extraction is verbatim: no paraphrasing or rewriting occurs.
    """
    path = Path(pdf_path)
    result = PdfExtractionResult(source_path=str(path))

    if not path.exists():
        result.errors.append(f"PDF file not found: {path}")
        return result

    try:
        reader = PdfReader(str(path))
    except Exception as exc:  # pragma: no cover - defensive
        result.errors.append(f"Failed to open PDF: {exc}")
        return result

    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:  # pragma: no cover - defensive
            result.errors.append(f"Failed to extract text from page {index}: {exc}")
            text = ""
        result.pages.append(PdfPage(page_number=index, text=text))

    return result