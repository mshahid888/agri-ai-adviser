"""
Milestone 10 tests: PDF & Agricultural Document Ingestion.

Tests verify PDF text extraction, page preservation, source/document metadata
association, conversion to knowledge Markdown, extraction-quality validation,
and the end-to-end ingestion pipeline.
"""
from pathlib import Path

import pytest

from app.document_metadata import (
    DocumentMetadata,
    build_document_metadata,
    validate_document_metadata,
)
from app.extraction_quality import assess_extraction_quality
from app.ingestion import ingest_pdf
from app.knowledge import parse_front_matter
from app.knowledge_converter import convert_to_knowledge_markdown
from app.pdf_extractor import PdfExtractionResult, PdfPage, extract_pdf_text
from app.source_registry import register_document_path

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
FIXTURE_PDF = FIXTURE_DIR / "sample_official.pdf"

KNOWN_PAGE1_TEXT = "Wheat Production Technology"
KNOWN_PAGE2_TEXT = "Rice Cultivation Notes"


# ============ M10.1 PDF extraction ============

def test_pdf_text_extraction_preserves_pages():
    result = extract_pdf_text(FIXTURE_PDF)

    assert result.page_count == 2
    assert [page.page_number for page in result.pages] == [1, 2]


def test_extraction_preserves_known_text():
    result = extract_pdf_text(FIXTURE_PDF)

    assert KNOWN_PAGE1_TEXT in result.pages[0].text
    assert KNOWN_PAGE2_TEXT in result.pages[1].text


def test_extraction_missing_file_reports_error():
    result = extract_pdf_text(FIXTURE_DIR / "does_not_exist.pdf")

    assert result.page_count == 0
    assert result.errors


# ============ M10.2 Source/document metadata ============

def test_document_metadata_links_to_source_registry():
    metadata = build_document_metadata(
        source_id="sahiwal-agriculture-extension",
        document_id="sahiwal-wheat-guide-2024",
        title="Sahiwal Wheat Production Guide",
        original_pdf_path=str(FIXTURE_PDF),
    )

    assert metadata.source_id == "sahiwal-agriculture-extension"
    assert metadata.district == "Sahiwal"
    assert metadata.province == "Punjab"
    assert metadata.status == "ingested"


def test_metadata_validation_rejects_unknown_source():
    metadata = DocumentMetadata(
        source_id="unknown-source",
        document_id="doc-1",
        title="Test",
        original_pdf_path="test.pdf",
    )
    issues = validate_document_metadata(metadata)

    assert any("Unknown source_id" in issue for issue in issues)


def test_metadata_validation_passes_for_valid_metadata():
    metadata = build_document_metadata(
        source_id="sahiwal-agriculture-extension",
        document_id="sahiwal-wheat-guide-2024",
        title="Sahiwal Wheat Production Guide",
        original_pdf_path=str(FIXTURE_PDF),
    )
    issues = validate_document_metadata(metadata)

    assert issues == []


# ============ M10.3 Conversion to knowledge Markdown ============

def test_conversion_produces_front_matter_and_body():
    extraction = extract_pdf_text(FIXTURE_PDF)
    metadata = build_document_metadata(
        source_id="sahiwal-agriculture-extension",
        document_id="sahiwal-wheat-guide-2024",
        title="Sahiwal Wheat Production Guide",
        original_pdf_path=str(FIXTURE_PDF),
    )

    output = convert_to_knowledge_markdown(extraction, metadata)

    assert "---" in output.markdown
    assert "source_id: sahiwal-agriculture-extension" in output.markdown
    assert "document_id: sahiwal-wheat-guide-2024" in output.markdown
    assert "content_status: extracted" in output.markdown
    assert KNOWN_PAGE1_TEXT in output.markdown
    assert KNOWN_PAGE2_TEXT in output.markdown


def test_converted_markdown_loads_in_knowledge_layer():
    extraction = extract_pdf_text(FIXTURE_PDF)
    metadata = build_document_metadata(
        source_id="sahiwal-agriculture-extension",
        document_id="sahiwal-wheat-guide-2024",
        title="Sahiwal Wheat Production Guide",
        original_pdf_path=str(FIXTURE_PDF),
    )

    output = convert_to_knowledge_markdown(extraction, metadata)
    parsed_metadata, body = parse_front_matter(output.markdown)

    assert parsed_metadata["source_id"] == "sahiwal-agriculture-extension"
    assert parsed_metadata["document_id"] == "sahiwal-wheat-guide-2024"
    assert parsed_metadata["content_status"] == "extracted"
    assert KNOWN_PAGE1_TEXT in body


# ============ M10.4 Extraction-quality validation ============

def test_extraction_quality_flags_empty_pages():
    extraction = PdfExtractionResult(
        source_path="test.pdf",
        pages=[PdfPage(page_number=1, text=""), PdfPage(page_number=2, text="")],
    )
    report = assess_extraction_quality(extraction)

    assert report.is_acceptable is False
    assert any("No text was extracted" in issue for issue in report.issues)


def test_extraction_quality_passes_for_good_extraction():
    extraction = extract_pdf_text(FIXTURE_PDF)
    report = assess_extraction_quality(extraction)

    assert report.is_acceptable is True
    assert report.page_count == 2
    assert report.total_chars > 0


# ============ End-to-end ingestion pipeline ============

def test_ingestion_pipeline_end_to_end(tmp_path, monkeypatch):
    import app.source_registry as source_registry

    # Use a temp registry dir so the real registry is untouched.
    temp_registry = tmp_path / "registry"
    temp_registry.mkdir()
    (temp_registry / "sahiwal_agriculture_extension.json").write_text(
        '{"source_id": "sahiwal-agriculture-extension", "title": "Sahiwal Agriculture Extension", '
        '"organization": "Agriculture Extension Department, Sahiwal", "source_type": "official_extension", '
        '"status": "registered", "document_path": ""}',
        encoding="utf-8",
    )
    monkeypatch.setattr(source_registry, "REGISTRY_DIR", temp_registry)

    result = ingest_pdf(
        pdf_path=FIXTURE_PDF,
        source_id="sahiwal-agriculture-extension",
        document_id="sahiwal-wheat-guide-2024",
        title="Sahiwal Wheat Production Guide",
        target_dir=tmp_path,
    )

    assert result.success is True
    assert result.knowledge_path
    assert result.quality_report is not None
    assert result.quality_report.is_acceptable is True
    assert result.metadata is not None
    assert result.metadata.source_id == "sahiwal-agriculture-extension"

    written = Path(result.knowledge_path)
    assert written.exists()
    content = written.read_text(encoding="utf-8")
    assert KNOWN_PAGE1_TEXT in content
    assert KNOWN_PAGE2_TEXT in content


def test_ingestion_rejects_unknown_source(tmp_path):
    result = ingest_pdf(
        pdf_path=FIXTURE_PDF,
        source_id="unknown-source",
        document_id="doc-1",
        title="Test",
        target_dir=tmp_path,
    )

    assert result.success is False
    assert any("Unknown source_id" in issue for issue in result.issues)


def test_ingestion_rejects_missing_pdf(tmp_path):
    result = ingest_pdf(
        pdf_path=FIXTURE_DIR / "missing.pdf",
        source_id="sahiwal-agriculture-extension",
        document_id="doc-1",
        title="Test",
        target_dir=tmp_path,
    )

    assert result.success is False
    assert any("PDF file not found" in issue for issue in result.issues)


# ============ Source registry document_path registration ============

def test_register_document_path_updates_registry(monkeypatch, tmp_path):
    import app.source_registry as source_registry

    # Use a temp registry dir so the real registry is untouched.
    temp_registry = tmp_path / "registry"
    temp_registry.mkdir()
    (temp_registry / "sahiwal_agriculture_extension.json").write_text(
        '{"source_id": "sahiwal-agriculture-extension", "title": "Sahiwal Agriculture Extension", '
        '"organization": "Agriculture Extension Department, Sahiwal", "source_type": "official_extension", '
        '"status": "registered", "document_path": ""}',
        encoding="utf-8",
    )
    monkeypatch.setattr(source_registry, "REGISTRY_DIR", temp_registry)

    registered = register_document_path("sahiwal-agriculture-extension", "knowledge/sources/originals/sample.pdf")

    assert registered == "knowledge/sources/originals/sample.pdf"
    data = (temp_registry / "sahiwal_agriculture_extension.json").read_text(encoding="utf-8")
    assert '"document_path": "knowledge/sources/originals/sample.pdf"' in data


def test_register_document_path_refuses_overwrite(monkeypatch, tmp_path):
    import app.source_registry as source_registry

    temp_registry = tmp_path / "registry"
    temp_registry.mkdir()
    (temp_registry / "sahiwal_agriculture_extension.json").write_text(
        '{"source_id": "sahiwal-agriculture-extension", "title": "Sahiwal Agriculture Extension", '
        '"organization": "Agriculture Extension Department, Sahiwal", "source_type": "official_extension", '
        '"status": "registered", "document_path": "existing.pdf"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(source_registry, "REGISTRY_DIR", temp_registry)

    with pytest.raises(ValueError, match="refusing to overwrite"):
        register_document_path("sahiwal-agriculture-extension", "new.pdf")
