"""PDF ingestion pipeline for the Agri-AI Adviser.

This module orchestrates the M10 pipeline:

    Original PDF
    -> text extraction (M10.1)
    -> source/document metadata (M10.2)
    -> conversion to knowledge Markdown (M10.3)
    -> extraction-quality validation (M10.4)
    -> curated knowledge Markdown written to the knowledge layer

This module is strictly additive. It does not modify any existing module.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.document_metadata import DocumentMetadata, build_document_metadata, validate_document_metadata
from app.extraction_quality import ExtractionQualityReport, assess_extraction_quality
from app.knowledge_converter import KnowledgeMarkdownOutput, convert_to_knowledge_markdown, write_knowledge_markdown
from app.pdf_extractor import PdfExtractionResult, extract_pdf_text
from app.source_registry import register_document_path


@dataclass
class IngestionResult:
    """Result of ingesting a PDF into the knowledge layer."""

    success: bool
    knowledge_path: str = ""
    quality_report: ExtractionQualityReport | None = None
    metadata: DocumentMetadata | None = None
    issues: list[str] = field(default_factory=list)


def ingest_pdf(
    pdf_path: str | Path,
    source_id: str,
    document_id: str,
    title: str,
    target_dir: str | Path,
    filename: str | None = None,
    **metadata_overrides,
) -> IngestionResult:
    """Ingest a PDF into the knowledge layer.

    Steps:
    1. Extract text from the PDF (verbatim, page-preserving).
    2. Validate extraction quality; abort if poor.
    3. Build and validate document metadata linked to the M9 source registry.
    4. Convert to knowledge Markdown (front matter + body).
    5. Write the Markdown to ``target_dir``.
    6. Register the original PDF path in the source registry.

    Returns an ``IngestionResult``.
    """
    path = Path(pdf_path)
    if not path.exists():
        return IngestionResult(success=False, issues=[f"PDF file not found: {path}"])

    # M10.1: text extraction
    extraction = extract_pdf_text(path)

    # M10.4: extraction-quality validation
    quality_report = assess_extraction_quality(extraction)
    if not quality_report.is_acceptable:
        return IngestionResult(
            success=False,
            quality_report=quality_report,
            issues=list(quality_report.issues),
        )

    # M10.2: source/document metadata
    try:
        metadata = build_document_metadata(
            source_id=source_id,
            document_id=document_id,
            title=title,
            original_pdf_path=str(path),
            **metadata_overrides,
        )
    except ValueError as exc:
        return IngestionResult(success=False, issues=[str(exc)])

    metadata_issues = validate_document_metadata(metadata)
    if metadata_issues:
        return IngestionResult(success=False, metadata=metadata, issues=metadata_issues)

    # M10.3: conversion to knowledge Markdown
    output = convert_to_knowledge_markdown(extraction, metadata)
    if not filename:
        filename = f"{document_id}.md"
    knowledge_path = write_knowledge_markdown(output, target_dir, filename)

    # Link original PDF path in the source registry
    register_document_path(source_id, str(path))

    return IngestionResult(
        success=True,
        knowledge_path=knowledge_path,
        quality_report=quality_report,
        metadata=metadata,
    )