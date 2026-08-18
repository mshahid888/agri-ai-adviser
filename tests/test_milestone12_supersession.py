"""
Milestone 12 tests: Automatic Supersession Linking.

Tests verify supersession detection, linking, and status updates for:
- first version (no previous)
- second version (supersedes first)
- multiple versions
- unchanged documents
- unrelated documents
- ambiguous metadata
- superseded/current status
"""
from pathlib import Path

import pytest

from app.knowledge import parse_front_matter
from app.supersession import (
    SupersessionResult,
    auto_link_supersession_on_ingest,
    find_previous_version,
    link_supersession,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
FIXTURE_PDF = FIXTURE_DIR / "sample_official.pdf"


def _write_doc(base: Path, rel: str, content: str) -> Path:
    path = base / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _make_doc(
    base: Path,
    rel: str,
    document_id: str,
    version: str,
    title: str = "Test Document",
    status: str = "active",
    content_status: str = "curated",
    supersedes: str = "",
    body: str = "Test content.",
) -> Path:
    supersedes_line = f"supersedes: {supersedes}\n" if supersedes else ""
    content = f"""---
title: {title}
document_id: {document_id}
version: {version}
content_status: {content_status}
source_type: official_extension
evidence_quality: general
status: {status}
{supersedes_line}organization: Test Org
last_updated: 2024-01-01
---
# {title}
{body}
"""
    return _write_doc(base, rel, content)


# ─── First version (no previous) ────────────────────────────────────────────

def test_first_version_has_no_previous(tmp_path):
    doc = _make_doc(tmp_path, "v1.md", "doc-1", "1.0")
    result = find_previous_version("doc-1", "1.0", tmp_path)
    assert result is None


def test_auto_link_first_version_does_not_link(tmp_path):
    doc = _make_doc(tmp_path, "v1.md", "doc-1", "1.0")
    result = auto_link_supersession_on_ingest(doc, tmp_path)
    assert result.linked is False
    assert result.new_document_id == "doc-1"


# ─── Second version (supersedes first) ──────────────────────────────────────

def test_second_version_finds_previous(tmp_path):
    _make_doc(tmp_path, "v1.md", "doc-1", "1.0", title="Doc V1")
    _make_doc(tmp_path, "v2.md", "doc-1", "2.0", title="Doc V2")

    previous = find_previous_version("doc-1", "2.0", tmp_path)
    assert previous is not None
    assert previous.title == "Doc V1"


def test_second_version_links_supersession(tmp_path):
    old_path = _make_doc(tmp_path, "v1.md", "doc-1", "1.0")
    new_path = _make_doc(tmp_path, "v2.md", "doc-1", "2.0")

    result = link_supersession(old_path, new_path, "2.0")
    assert result.linked is True
    assert result.new_document_id == "doc-1"

    old_content = old_path.read_text(encoding="utf-8")
    old_meta, _ = parse_front_matter(old_content)
    assert old_meta.get("status") == "superseded"

    new_content = new_path.read_text(encoding="utf-8")
    new_meta, _ = parse_front_matter(new_content)
    assert new_meta.get("supersedes") == "1.0"


def test_auto_link_second_version(tmp_path):
    _make_doc(tmp_path, "v1.md", "doc-1", "1.0")
    new_path = _make_doc(tmp_path, "v2.md", "doc-1", "2.0")

    result = auto_link_supersession_on_ingest(new_path, tmp_path)
    assert result.linked is True


# ─── Multiple versions ──────────────────────────────────────────────────────

def test_third_version_supersedes_second(tmp_path):
    _make_doc(tmp_path, "v1.md", "doc-1", "1.0")
    _make_doc(tmp_path, "v2.md", "doc-1", "2.0")
    new_path = _make_doc(tmp_path, "v3.md", "doc-1", "3.0")

    previous = find_previous_version("doc-1", "3.0", tmp_path)
    assert previous is not None
    assert "v2.md" in previous.path

    result = auto_link_supersession_on_ingest(new_path, tmp_path)
    assert result.linked is True


# ─── Unchanged document ─────────────────────────────────────────────────────

def test_unchanged_document_does_not_create_supersession(tmp_path):
    _make_doc(tmp_path, "v1.md", "doc-1", "1.0")
    new_path = _make_doc(tmp_path, "v1_copy.md", "doc-1", "1.0")

    result = auto_link_supersession_on_ingest(new_path, tmp_path)
    assert result.linked is False


# ─── Unrelated documents ────────────────────────────────────────────────────

def test_unrelated_documents_do_not_link(tmp_path):
    _make_doc(tmp_path, "a.md", "doc-a", "1.0")
    new_path = _make_doc(tmp_path, "b.md", "doc-b", "1.0")

    result = auto_link_supersession_on_ingest(new_path, tmp_path)
    assert result.linked is False


# ─── Ambiguous metadata ─────────────────────────────────────────────────────

def test_no_document_id_does_not_link(tmp_path):
    _write_doc(tmp_path, "v1.md", """---
title: Test
version: 1.0
content_status: curated
source_type: official_extension
evidence_quality: general
status: active
organization: Test
last_updated: 2024-01-01
---
# Test
Content.
""")
    new_path = _write_doc(tmp_path, "v2.md", """---
title: Test V2
version: 2.0
content_status: curated
source_type: official_extension
evidence_quality: general
status: active
organization: Test
last_updated: 2024-01-01
---
# Test V2
Content.
""")
    result = auto_link_supersession_on_ingest(new_path, tmp_path)
    assert result.linked is False
    assert any("document_id" in i for i in result.issues)


def test_mismatched_document_ids_rejected(tmp_path):
    old_path = _make_doc(tmp_path, "v1.md", "doc-a", "1.0")
    new_path = _make_doc(tmp_path, "v2.md", "doc-b", "2.0")

    result = link_supersession(old_path, new_path, "2.0")
    assert result.linked is False
    assert any("do not match" in i for i in result.issues)


# ─── Superseded/current status ──────────────────────────────────────────────

def test_superseded_old_document_not_linked(tmp_path):
    _make_doc(tmp_path, "v1.md", "doc-1", "1.0", status="superseded")
    new_path = _make_doc(tmp_path, "v2.md", "doc-1", "2.0")

    result = auto_link_supersession_on_ingest(new_path, tmp_path)
    assert result.linked is False


def test_archived_old_document_not_linked(tmp_path):
    _make_doc(tmp_path, "v1.md", "doc-1", "1.0", status="archived")
    new_path = _make_doc(tmp_path, "v2.md", "doc-1", "2.0")

    result = auto_link_supersession_on_ingest(new_path, tmp_path)
    assert result.linked is False


# ─── Edge cases ──────────────────────────────────────────────────────────────

def test_link_supersession_missing_old_file(tmp_path):
    new_path = _make_doc(tmp_path, "v2.md", "doc-1", "2.0")
    result = link_supersession(tmp_path / "nonexistent.md", new_path, "2.0")
    assert result.linked is False
    assert any("not found" in i for i in result.issues)


def test_link_supersession_missing_new_file(tmp_path):
    old_path = _make_doc(tmp_path, "v1.md", "doc-1", "1.0")
    result = link_supersession(old_path, tmp_path / "nonexistent.md", "2.0")
    assert result.linked is False
    assert any("not found" in i for i in result.issues)


def test_old_document_with_no_front_matter(tmp_path):
    old_path = _write_doc(tmp_path, "v1.md", "No front matter here.")
    new_path = _make_doc(tmp_path, "v2.md", "doc-1", "2.0")

    result = link_supersession(old_path, new_path, "2.0")
    assert result.linked is False
    assert any("no front matter" in i.lower() for i in result.issues)


def test_link_preserves_old_content(tmp_path):
    old_path = _make_doc(tmp_path, "v1.md", "doc-1", "1.0", body="Original content preserved.")
    new_path = _make_doc(tmp_path, "v2.md", "doc-1", "2.0")

    link_supersession(old_path, new_path, "2.0")
    old_content = old_path.read_text(encoding="utf-8")
    assert "Original content preserved." in old_content
