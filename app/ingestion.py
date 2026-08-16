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
from app.knowledge import parse_front_matter
from app.knowledge_converter import KnowledgeMarkdownOutput, convert_to_knowledge_markdown, write_knowledge_markdown
from app.knowledge_schema import validate_knowledge_metadata
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


@dataclass
class BatchIngestionResult:
    """Result of batch-ingesting multiple PDFs."""

    results: list[IngestionResult] = field(default_factory=list)
    succeeded: int = 0
    failed: int = 0
    total: int = 0


def _document_id_exists(target_dir: Path, document_id: str) -> bool:
    """Check if a knowledge document with the given document_id already exists."""
    if not target_dir.exists():
        return False
    for path in target_dir.rglob("*.md"):
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        metadata, _ = parse_front_matter(content)
        if metadata.get("document_id") == document_id:
            return True
    return False


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
    5. Validate the generated front matter against the production schema.
    6. Write the Markdown to ``target_dir``.
    7. Register the original PDF path in the source registry.

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

    # M11: deduplication check (before conversion)
    target = Path(target_dir)
    if _document_id_exists(target, document_id):
        return IngestionResult(
            success=False,
            metadata=metadata,
            issues=[f"Duplicate: a knowledge document with document_id '{document_id}' already exists in {target_dir}"],
        )

    # M10.3: conversion to knowledge Markdown
    output = convert_to_knowledge_markdown(extraction, metadata)
    if not filename:
        filename = f"{document_id}.md"

    # M11: validate generated front matter before writing
    parsed_meta, _ = parse_front_matter(output.markdown)
    schema_result = validate_knowledge_metadata(parsed_meta, document_path=filename)
    if not schema_result.is_valid:
        return IngestionResult(
            success=False,
            metadata=metadata,
            issues=[f"Schema validation failed: {issue}" for issue in schema_result.errors],
        )

    # M11: section detection (additive, does not alter source text)
    # Sections are detected via heading lines but the original text is preserved verbatim.

    knowledge_path = write_knowledge_markdown(output, target_dir, filename)

    # Link original PDF path in the source registry
    register_document_path(source_id, str(path))

    return IngestionResult(
        success=True,
        knowledge_path=knowledge_path,
        quality_report=quality_report,
        metadata=metadata,
    )


def ingest_pdfs(
    items: list[dict],
    target_dir: str | Path,
) -> BatchIngestionResult:
    """Ingest multiple PDFs in a single batch.

    Each item in ``items`` must be a dict with keys:
        pdf_path, source_id, document_id, title

    Optional keys (forwarded as ``**metadata_overrides``):
        filename, crop, region, province, district, topic, etc.

    One failed document does not prevent other documents from being ingested.
    Returns a ``BatchIngestionResult`` with per-document outcomes.
    """
    batch = BatchIngestionResult(total=len(items))
    for item in items:
        item_copy = dict(item)
        pdf_path = item_copy.pop("pdf_path")
        source_id = item_copy.pop("source_id")
        document_id = item_copy.pop("document_id")
        title = item_copy.pop("title")
        result = ingest_pdf(
            pdf_path=pdf_path,
            source_id=source_id,
            document_id=document_id,
            title=title,
            target_dir=target_dir,
            **item_copy,
        )
        batch.results.append(result)
        if result.success:
            batch.succeeded += 1
        else:
            batch.failed += 1
    return batch
