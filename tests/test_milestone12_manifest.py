"""
Milestone 12 tests: Knowledge Versioning with Manifest.

Tests verify manifest creation, loading, updates, duplicate detection,
changed document detection, missing/stale/corrupted manifest handling,
and invalid metadata handling.
"""
from pathlib import Path

import pytest

from app.knowledge_manifest import (
    KnowledgeManifest,
    ManifestEntry,
    build_manifest_from_knowledge_base,
    compare_manifests,
    compute_content_hash,
    load_manifest,
    save_manifest,
)


# ─── Content hash ────────────────────────────────────────────────────────────

def test_content_hash_is_deterministic():
    hash1 = compute_content_hash("Hello, world!")
    hash2 = compute_content_hash("Hello, world!")
    assert hash1 == hash2


def test_content_hash_differs_for_different_content():
    hash1 = compute_content_hash("Hello, world!")
    hash2 = compute_content_hash("Goodbye, world!")
    assert hash1 != hash2


def test_content_hash_is_sha256():
    h = compute_content_hash("test")
    assert len(h) == 64


# ─── Manifest entry ─────────────────────────────────────────────────────────

def test_manifest_entry_to_dict_and_from_dict():
    entry = ManifestEntry(
        document_id="doc-1",
        path="knowledge/crops/wheat.md",
        title="Wheat",
        source_id="test-source",
        version="1.0",
        status="active",
        content_hash="abc123",
    )
    d = entry.to_dict()
    restored = ManifestEntry.from_dict(d)
    assert restored.document_id == "doc-1"
    assert restored.path == "knowledge/crops/wheat.md"
    assert restored.version == "1.0"
    assert restored.content_hash == "abc123"


def test_manifest_entry_from_dict_skips_unknown_fields():
    entry = ManifestEntry.from_dict({"document_id": "x", "unknown_field": "ignored"})
    assert entry.document_id == "x"


# ─── Manifest data structure ─────────────────────────────────────────────────

def test_manifest_to_dict_and_from_dict():
    manifest = KnowledgeManifest(entries=[
        ManifestEntry(document_id="a", path="a.md", version="1.0"),
        ManifestEntry(document_id="b", path="b.md", version="2.0"),
    ])
    d = manifest.to_dict()
    restored = KnowledgeManifest.from_dict(d)
    assert len(restored.entries) == 2
    assert restored.version == "1.0"


def test_manifest_from_dict_rejects_non_dict():
    with pytest.raises(ValueError, match="dictionary"):
        KnowledgeManifest.from_dict("not a dict")


def test_manifest_get_entry_by_document_id():
    manifest = KnowledgeManifest(entries=[
        ManifestEntry(document_id="doc-1", path="a.md"),
        ManifestEntry(document_id="doc-2", path="b.md"),
    ])
    entry = manifest.get_entry("doc-2")
    assert entry is not None
    assert entry.path == "b.md"
    assert manifest.get_entry("nonexistent") is None


def test_manifest_get_entry_by_path():
    manifest = KnowledgeManifest(entries=[
        ManifestEntry(document_id="doc-1", path="knowledge/crops/wheat.md"),
    ])
    assert manifest.get_entry_by_path("knowledge/crops/wheat.md") is not None
    assert manifest.get_entry_by_path("knowledge/crops/rice.md") is None


def test_manifest_has_document():
    manifest = KnowledgeManifest(entries=[
        ManifestEntry(document_id="doc-1", path="a.md"),
    ])
    assert manifest.has_document("doc-1") is True
    assert manifest.has_document("doc-2") is False


# ─── Build manifest from knowledge base ─────────────────────────────────────

def test_build_manifest_from_knowledge_base():
    manifest = build_manifest_from_knowledge_base()
    assert len(manifest.entries) > 0
    for entry in manifest.entries:
        assert entry.path
        assert entry.content_hash


def test_manifest_entries_have_source_ids_for_m9_docs():
    manifest = build_manifest_from_knowledge_base()
    m9_docs = [e for e in manifest.entries if e.source_id]
    assert len(m9_docs) > 0
    for entry in m9_docs:
        assert entry.path
        assert entry.source_id


# ─── Save and load manifest ─────────────────────────────────────────────────

def test_save_and_load_manifest(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest = KnowledgeManifest(entries=[
        ManifestEntry(document_id="doc-1", path="a.md", content_hash="abc"),
    ])
    save_manifest(manifest, manifest_path)
    loaded = load_manifest(manifest_path)
    assert len(loaded.entries) == 1
    assert loaded.entries[0].document_id == "doc-1"
    assert loaded.entries[0].content_hash == "abc"


def test_load_manifest_returns_empty_for_missing_file(tmp_path):
    manifest = load_manifest(tmp_path / "nonexistent.json")
    assert len(manifest.entries) == 0


def test_load_manifest_returns_empty_for_corrupted_file(tmp_path):
    manifest_path = tmp_path / "corrupted.json"
    manifest_path.write_text("not valid json {{{", encoding="utf-8")
    manifest = load_manifest(manifest_path)
    assert len(manifest.entries) == 0


def test_load_manifest_returns_empty_for_invalid_structure(tmp_path):
    manifest_path = tmp_path / "invalid.json"
    manifest_path.write_text('"just a string"', encoding="utf-8")
    manifest = load_manifest(manifest_path)
    assert len(manifest.entries) == 0


# ─── Duplicate documents ─────────────────────────────────────────────────────

def test_duplicate_document_ids_in_manifest():
    manifest = KnowledgeManifest(entries=[
        ManifestEntry(document_id="doc-1", path="a.md"),
        ManifestEntry(document_id="doc-1", path="b.md"),
    ])
    entry = manifest.get_entry("doc-1")
    assert entry is not None
    assert entry.path == "a.md"


# ─── Changed documents ──────────────────────────────────────────────────────

def test_compare_manifests_detects_added():
    old = KnowledgeManifest(entries=[
        ManifestEntry(document_id="doc-1", path="a.md", content_hash="h1"),
    ])
    new = KnowledgeManifest(entries=[
        ManifestEntry(document_id="doc-1", path="a.md", content_hash="h1"),
        ManifestEntry(document_id="doc-2", path="b.md", content_hash="h2"),
    ])
    result = compare_manifests(old, new)
    assert len(result["added"]) == 1
    assert result["added"][0].document_id == "doc-2"
    assert len(result["removed"]) == 0
    assert len(result["changed"]) == 0
    assert len(result["unchanged"]) == 1


def test_compare_manifests_detects_removed():
    old = KnowledgeManifest(entries=[
        ManifestEntry(document_id="doc-1", path="a.md", content_hash="h1"),
        ManifestEntry(document_id="doc-2", path="b.md", content_hash="h2"),
    ])
    new = KnowledgeManifest(entries=[
        ManifestEntry(document_id="doc-1", path="a.md", content_hash="h1"),
    ])
    result = compare_manifests(old, new)
    assert len(result["added"]) == 0
    assert len(result["removed"]) == 1
    assert result["removed"][0].document_id == "doc-2"


def test_compare_manifests_detects_changed_hash():
    old = KnowledgeManifest(entries=[
        ManifestEntry(document_id="doc-1", path="a.md", content_hash="old_hash", version="1.0"),
    ])
    new = KnowledgeManifest(entries=[
        ManifestEntry(document_id="doc-1", path="a.md", content_hash="new_hash", version="1.0"),
    ])
    result = compare_manifests(old, new)
    assert len(result["changed"]) == 1
    assert len(result["unchanged"]) == 0


def test_compare_manifests_detects_changed_version():
    old = KnowledgeManifest(entries=[
        ManifestEntry(document_id="doc-1", path="a.md", content_hash="h1", version="1.0"),
    ])
    new = KnowledgeManifest(entries=[
        ManifestEntry(document_id="doc-1", path="a.md", content_hash="h1", version="2.0"),
    ])
    result = compare_manifests(old, new)
    assert len(result["changed"]) == 1


def test_compare_manifests_detects_changed_status():
    old = KnowledgeManifest(entries=[
        ManifestEntry(document_id="doc-1", path="a.md", content_hash="h1", status="active"),
    ])
    new = KnowledgeManifest(entries=[
        ManifestEntry(document_id="doc-1", path="a.md", content_hash="h1", status="superseded"),
    ])
    result = compare_manifests(old, new)
    assert len(result["changed"]) == 1


def test_compare_manifests_unchanged():
    old = KnowledgeManifest(entries=[
        ManifestEntry(document_id="doc-1", path="a.md", content_hash="h1", version="1.0", status="active"),
    ])
    new = KnowledgeManifest(entries=[
        ManifestEntry(document_id="doc-1", path="a.md", content_hash="h1", version="1.0", status="active"),
    ])
    result = compare_manifests(old, new)
    assert len(result["added"]) == 0
    assert len(result["removed"]) == 0
    assert len(result["changed"]) == 0
    assert len(result["unchanged"]) == 1


def test_compare_manifests_empty_both():
    old = KnowledgeManifest()
    new = KnowledgeManifest()
    result = compare_manifests(old, new)
    assert len(result["added"]) == 0
    assert len(result["removed"]) == 0
    assert len(result["changed"]) == 0
    assert len(result["unchanged"]) == 0


# ─── Stale manifest ─────────────────────────────────────────────────────────

def test_stale_manifest_is_safe():
    stale_path = Path(__file__).parent.parent / "knowledge" / "manifest.json"
    if stale_path.exists():
        stale_path.unlink()
    manifest = load_manifest(stale_path)
    assert len(manifest.entries) == 0


# ─── Invalid metadata ───────────────────────────────────────────────────────

def test_manifest_entry_with_empty_metadata():
    entry = ManifestEntry()
    d = entry.to_dict()
    restored = ManifestEntry.from_dict({})
    assert restored.document_id == ""
    assert restored.path == ""
    assert restored.version == ""


# ─── Backward compatibility ─────────────────────────────────────────────────

def test_manifest_does_not_affect_knowledge_loading():
    from app.knowledge import load_knowledge_documents
    docs_before = load_knowledge_documents()
    manifest = build_manifest_from_knowledge_base()
    docs_after = load_knowledge_documents()
    assert len(docs_before) == len(docs_after)
