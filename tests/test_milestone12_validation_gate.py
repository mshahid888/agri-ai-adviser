"""
Milestone 12 tests: Validation CI Gate.

Tests verify the validation gate can:
- validate the existing knowledge base
- detect invalid documents
- produce useful error messages
- pass when all documents are valid
"""
from pathlib import Path

import pytest

from app.knowledge import KnowledgeDocument
from app.knowledge_schema import SchemaValidationResult, validate_knowledge_metadata
from app.validation_gate import (
    ValidationGateResult,
    run_validation_gate,
    validate_knowledge_base,
)


# ─── Validation gate on the real knowledge base ─────────────────────────────

def test_validation_gate_passes_on_current_knowledge_base():
    result = run_validation_gate()
    assert result.passed is True
    assert result.invalid_documents == 0
    assert result.total_documents > 0


def test_validation_gate_returns_per_document_results():
    result = run_validation_gate()
    assert len(result.results) == result.total_documents
    for r in result.results:
        assert hasattr(r, "is_valid")
        assert hasattr(r, "errors")
        assert hasattr(r, "warnings")


def test_validate_knowledge_base_convenience_function():
    passed, summary = validate_knowledge_base()
    assert passed is True
    assert "PASS" in summary
    assert "Total documents" in summary


def test_validation_gate_summary_contains_expected_fields():
    result = run_validation_gate()
    summary = result.summary()
    assert "Validation Gate Result:" in summary
    assert "Total documents:" in summary
    assert "Valid:" in summary
    assert "Invalid:" in summary
    assert "Errors:" in summary
    assert "Warnings:" in summary


def test_validation_gate_error_count():
    result = run_validation_gate()
    assert result.error_count == 0


# ─── Validation gate detects invalid documents ──────────────────────────────

def test_validation_gate_flags_missing_content_status():
    invalid_doc = KnowledgeDocument(
        path="knowledge/test/invalid.md",
        title="Invalid Document",
        content="Some content",
        metadata={"title": "Invalid Document"},
    )
    from app.knowledge_schema import validate_knowledge_document
    result = validate_knowledge_document(invalid_doc)
    assert result.is_valid is False
    assert any("content_status" in e for e in result.errors)


def test_validation_gate_flags_invalid_enum_value():
    metadata = {
        "title": "Test",
        "content_status": "invalid_status",
    }
    result = validate_knowledge_metadata(metadata)
    assert result.is_valid is False
    assert any("content_status" in e for e in result.errors)


def test_validation_gate_passes_for_valid_placeholder():
    metadata = {
        "title": "Test Placeholder",
        "content_status": "placeholder",
    }
    result = validate_knowledge_metadata(metadata)
    assert result.is_valid is True


def test_validation_gate_passes_for_valid_extracted():
    metadata = {
        "title": "Test Extracted",
        "content_status": "extracted",
        "source_id": "sahiwal-agriculture-extension",
        "document_id": "test-doc-1",
        "source_type": "official_extension",
        "version": "1.0",
        "status": "active",
        "evidence_quality": "general",
        "organization": "Test Org",
        "last_updated": "2024-01-01",
    }
    result = validate_knowledge_metadata(metadata)
    assert result.is_valid is True


# ─── Validation gate with filtered directory ─────────────────────────────────

def test_validation_gate_with_directory_filter():
    result = run_validation_gate(knowledge_dir="knowledge/crops")
    assert result.passed is True
    assert result.total_documents > 0
    for r in result.results:
        assert "crops" in r.document_path


# ─── Validation gate result dataclass ───────────────────────────────────────

def test_validation_gate_result_passed_true_when_no_invalid():
    result = ValidationGateResult(total_documents=5, valid_documents=5, invalid_documents=0)
    assert result.passed is True


def test_validation_gate_result_passed_false_when_invalid():
    result = ValidationGateResult(total_documents=5, valid_documents=3, invalid_documents=2)
    assert result.passed is False


def test_validation_gate_result_error_count():
    result = ValidationGateResult()
    result.results = [
        SchemaValidationResult(document_path="a.md", is_valid=False, errors=["err1", "err2"]),
        SchemaValidationResult(document_path="b.md", is_valid=True),
    ]
    assert result.error_count == 2


def test_validation_gate_result_warning_count():
    result = ValidationGateResult()
    result.results = [
        SchemaValidationResult(document_path="a.md", is_valid=True, warnings=["warn1"]),
        SchemaValidationResult(document_path="b.md", is_valid=True, warnings=["warn2", "warn3"]),
    ]
    assert result.warning_count == 3
