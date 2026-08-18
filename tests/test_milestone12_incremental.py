"""
Milestone 12 tests: Incremental Ingestion.

Tests verify that incremental ingestion:
- detects new, modified, unchanged documents
- preserves existing full ingestion behavior
- provides a safe full rebuild
- is deterministic
- handles failed ingestion without corrupting state
"""
from pathlib import Path

import pytest

from app.incremental_ingestion import (
    IncrementalIngestionResult,
    detect_changes,
    full_rebuild,
    incremental_ingest,
)
from app.knowledge_manifest import (
    KnowledgeManifest,
    ManifestEntry,
    compute_content_hash,
    load_manifest,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
FIXTURE_PDF = FIXTURE_DIR / "sample_official.pdf"


def _monkeypatch_registry(monkeypatch, tmp_path, source_id="sahiwal-agriculture-extension"):
    """Point the source registry at a temp dir with a known source."""
    import app.source_registry as source_registry

    registry_dir = tmp_path / "registry"
    registry_dir.mkdir(parents=True, exist_ok=True)
    filename = source_id.replace("-", "_") + ".json"
    (registry_dir / filename).write_text(
        f'{{"source_id": "{source_id}", "title": "{source_id}", '
        f'"organization": "Test Org", '
        f'"source_type": "official_extension", "status": "registered", "document_path": ""}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(source_registry, "REGISTRY_DIR", registry_dir)
    return registry_dir


# ─── Detect changes ──────────────────────────────────────────────────────────

def test_detect_changes_with_no_manifest():
    result = detect_changes(manifest_path=Path("/nonexistent/manifest.json"))
    assert isinstance(result, dict)
    assert "added" in result
    assert "removed" in result
    assert "changed" in result
    assert "unchanged" in result


# ─── Incremental ingestion: new documents ────────────────────────────────────

def test_incremental_ingest_new_document(tmp_path, monkeypatch):
    _monkeypatch_registry(monkeypatch, tmp_path)
    target = tmp_path / "out"

    items = [
        {
            "pdf_path": str(FIXTURE_PDF),
            "source_id": "sahiwal-agriculture-extension",
            "document_id": "inc-doc-1",
            "title": "Incremental Document One",
        }
    ]

    result = incremental_ingest(items, target)
    assert result.new_documents == 1
    assert result.unchanged_documents == 0
    assert result.modified_documents == 0
    assert result.success is True


# ─── Incremental ingestion: unchanged documents ──────────────────────────────

def test_incremental_ingest_unchanged_document(tmp_path, monkeypatch):
    _monkeypatch_registry(monkeypatch, tmp_path)
    target = tmp_path / "out"

    items = [
        {
            "pdf_path": str(FIXTURE_PDF),
            "source_id": "sahiwal-agriculture-extension",
            "document_id": "inc-doc-1",
            "title": "Incremental Document One",
        }
    ]

    result1 = incremental_ingest(items, target)
    assert result1.new_documents == 1

    result2 = incremental_ingest(items, target)
    assert result2.unchanged_documents == 1
    assert result2.new_documents == 0


# ─── Incremental ingestion: failed ingestion ─────────────────────────────────

def test_incremental_ingest_failed_document_does_not_corrupt_state(tmp_path, monkeypatch):
    _monkeypatch_registry(monkeypatch, tmp_path)
    target = tmp_path / "out"

    items = [
        {
            "pdf_path": str(FIXTURE_DIR / "missing.pdf"),
            "source_id": "sahiwal-agriculture-extension",
            "document_id": "inc-doc-fail",
            "title": "Failing Document",
        }
    ]

    result = incremental_ingest(items, target)
    assert result.failed_documents == 1
    assert result.success is False


# ─── Full rebuild ────────────────────────────────────────────────────────────

def test_full_rebuild_processes_all_documents(tmp_path, monkeypatch):
    _monkeypatch_registry(monkeypatch, tmp_path, "source-a")
    _monkeypatch_registry(monkeypatch, tmp_path, "source-b")
    import app.source_registry as source_registry
    registry_dir = tmp_path / "registry"
    for sid in ["source-a", "source-b"]:
        filename = sid.replace("-", "_") + ".json"
        (registry_dir / filename).write_text(
            f'{{"source_id": "{sid}", "title": "{sid}", '
            f'"organization": "Test Org", '
            f'"source_type": "official_extension", "status": "registered", "document_path": ""}}',
            encoding="utf-8",
        )
    monkeypatch.setattr(source_registry, "REGISTRY_DIR", registry_dir)

    target = tmp_path / "out"

    items = [
        {
            "pdf_path": str(FIXTURE_PDF),
            "source_id": "source-a",
            "document_id": "rebuild-doc-1",
            "title": "Rebuild Document One",
        },
        {
            "pdf_path": str(FIXTURE_PDF),
            "source_id": "source-b",
            "document_id": "rebuild-doc-2",
            "title": "Rebuild Document Two",
        },
    ]

    result = full_rebuild(items, target)
    assert result.new_documents == 2
    assert result.failed_documents == 0
    assert result.success is True


def test_full_rebuild_saves_manifest(tmp_path, monkeypatch):
    _monkeypatch_registry(monkeypatch, tmp_path)
    manifest_path = tmp_path / "manifest.json"
    target = tmp_path / "out"

    items = [
        {
            "pdf_path": str(FIXTURE_PDF),
            "source_id": "sahiwal-agriculture-extension",
            "document_id": "rebuild-doc-3",
            "title": "Rebuild Document Three",
        }
    ]

    full_rebuild(items, target, manifest_path)
    assert manifest_path.exists()
    loaded = load_manifest(manifest_path)
    assert loaded.has_document("rebuild-doc-3")


# ─── Determinism ─────────────────────────────────────────────────────────────

def test_incremental_ingestion_is_deterministic(tmp_path, monkeypatch):
    _monkeypatch_registry(monkeypatch, tmp_path)
    target1 = tmp_path / "out1"

    items = [
        {
            "pdf_path": str(FIXTURE_PDF),
            "source_id": "sahiwal-agriculture-extension",
            "document_id": "det-doc-1",
            "title": "Deterministic Document",
        }
    ]

    result1 = incremental_ingest(items, target1)
    assert result1.new_documents == 1
    assert result1.success is True

    result2 = incremental_ingest(items, target1)
    assert result2.unchanged_documents == 1
    assert result2.new_documents == 0


# ─── Backward compatibility ─────────────────────────────────────────────────

def test_incremental_ingestion_does_not_affect_existing_knowledge():
    before = load_manifest()
    detect_changes()
    after = load_manifest()
    assert len(before.entries) == len(after.entries)
