"""Automatic supersession linking for the Agri-AI Adviser.

When a new version of an existing knowledge document is ingested, this module
automatically identifies the previous version and establishes the appropriate
supersession relationship.

It uses existing provenance and metadata concepts from M11. It does not delete
historical knowledge, preserves provenance, and clearly distinguishes
current/active knowledge from superseded knowledge.

This module is strictly additive. It does not modify any existing module.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.knowledge import (
    KnowledgeDocument,
    load_knowledge_documents,
    parse_front_matter,
)
from app.knowledge_manifest import (
    KnowledgeManifest,
    ManifestEntry,
    build_manifest_entry_from_document,
)
from app.knowledge_schema import validate_knowledge_metadata


@dataclass
class SupersessionResult:
    """Result of an automatic supersession linking operation."""

    new_document_id: str = ""
    old_document_path: str = ""
    new_document_path: str = ""
    linked: bool = False
    issues: list[str] = field(default_factory=list)


def _version_tuple(version_str: str) -> tuple[int, ...]:
    """Convert a version string to a comparable tuple of integers."""
    import re
    if not version_str:
        return (0,)
    numbers = tuple(int(part) for part in re.findall(r"\d+", version_str))
    return numbers if numbers else (0,)


def find_previous_version(
    document_id: str,
    current_version: str,
    target_dir: str | Path,
) -> KnowledgeDocument | None:
    """Find the previous version of a document with the given document_id.

    Scans the target directory for documents with the same document_id
    but a lower version number. Returns the most recent previous version,
    or None if no previous version exists.
    """
    if not document_id:
        return None

    target = Path(target_dir)
    if not target.exists():
        return None

    candidates: list[tuple[tuple[int, ...], KnowledgeDocument]] = []

    for md_path in target.rglob("*.md"):
        if not md_path.is_file():
            continue
        content = md_path.read_text(encoding="utf-8")
        metadata, body = parse_front_matter(content)
        if not metadata:
            continue

        if metadata.get("document_id") != document_id:
            continue

        candidate_version = metadata.get("version", "")
        if candidate_version == current_version:
            continue

        status = metadata.get("status", "active")
        if status in {"superseded", "archived"}:
            continue

        v_tuple = _version_tuple(candidate_version)
        if v_tuple < _version_tuple(current_version):
            doc = KnowledgeDocument(
                path=str(md_path).replace("\\", "/").replace(str(target.parent).replace("\\", "/") + "/", ""),
                title=metadata.get("title", ""),
                content=body,
                metadata=metadata,
            )
            candidates.append((v_tuple, doc))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def link_supersession(
    old_doc_path: str | Path,
    new_doc_path: str | Path,
    new_version: str,
) -> SupersessionResult:
    """Link supersession between an old and new document.

    Updates the old document's ``status`` to ``superseded`` and adds
    ``supersedes`` to the new document if appropriate.

    Returns a ``SupersessionResult``.
    """
    old_path = Path(old_doc_path)
    new_path = Path(new_doc_path)

    if not old_path.exists():
        return SupersessionResult(issues=[f"Old document not found: {old_path}"])
    if not new_path.exists():
        return SupersessionResult(issues=[f"New document not found: {new_path}"])

    old_content = old_path.read_text(encoding="utf-8")
    new_content = new_path.read_text(encoding="utf-8")

    old_meta, old_body = parse_front_matter(old_content)
    new_meta, new_body = parse_front_matter(new_content)

    if not old_meta:
        return SupersessionResult(issues=["Old document has no front matter"])
    if not new_meta:
        return SupersessionResult(issues=["New document has no front matter"])

    old_doc_id = old_meta.get("document_id", "")
    new_doc_id = new_meta.get("document_id", "")
    if old_doc_id != new_doc_id:
        return SupersessionResult(issues=[
            f"Document IDs do not match: old={old_doc_id}, new={new_doc_id}"
        ])

    old_version = old_meta.get("version", "")
    if _version_tuple(new_version) <= _version_tuple(old_version):
        return SupersessionResult(issues=[
            f"New version {new_version} is not newer than old version {old_version}"
        ])

    old_status = old_meta.get("status", "active")
    if old_status in {"superseded", "archived"}:
        return SupersessionResult(issues=[
            f"Old document already has status '{old_status}'"
        ])

    old_lines = old_content.splitlines(keepends=True)
    in_front_matter = False
    status_updated = False
    for i, line in enumerate(old_lines):
        stripped = line.strip()
        if stripped == "---":
            if not in_front_matter:
                in_front_matter = True
                continue
            else:
                break
        if in_front_matter and stripped.startswith("status:"):
            old_lines[i] = f"status: superseded\n"
            status_updated = True
            break

    if status_updated:
        old_path.write_text("".join(old_lines), encoding="utf-8")

    new_lines = new_content.splitlines(keepends=True)
    in_front_matter = False
    has_supersedes = False
    closing_dd_idx = None
    for i, line in enumerate(new_lines):
        stripped = line.strip()
        if stripped == "---":
            if not in_front_matter:
                in_front_matter = True
                continue
            else:
                closing_dd_idx = i
                break
        if in_front_matter and stripped.startswith("supersedes:"):
            has_supersedes = True
            break

    if not has_supersedes and closing_dd_idx is not None:
        new_lines.insert(closing_dd_idx, f"supersedes: {old_version}\n")
        new_path.write_text("".join(new_lines), encoding="utf-8")

    return SupersessionResult(
        new_document_id=new_doc_id,
        old_document_path=str(old_path),
        new_document_path=str(new_path),
        linked=True,
    )


def auto_link_supersession_on_ingest(
    new_doc_path: str | Path,
    target_dir: str | Path,
) -> SupersessionResult:
    """Automatically detect and link supersession for a newly ingested document.

    Finds the previous version (if any) and establishes the supersession
    relationship.

    Returns a ``SupersessionResult``.
    """
    new_path = Path(new_doc_path)
    if not new_path.exists():
        return SupersessionResult(issues=[f"New document not found: {new_path}"])

    content = new_path.read_text(encoding="utf-8")
    metadata, _ = parse_front_matter(content)
    if not metadata:
        return SupersessionResult(issues=["New document has no front matter"])

    document_id = metadata.get("document_id", "")
    version = metadata.get("version", "")

    if not document_id:
        return SupersessionResult(issues=["New document has no document_id"])

    old_doc = find_previous_version(document_id, version, target_dir)
    if old_doc is None:
        return SupersessionResult(
            new_document_id=document_id,
            new_document_path=str(new_path),
            linked=False,
        )

    old_path = Path(old_doc.path)
    if not old_path.is_absolute():
        old_path = Path(target_dir) / old_path
    
    # Ensure it's inside target_dir or just exists
    if not old_path.exists():
        # Maybe it's a relative path from the knowledge directory itself
        possible_path = Path(target_dir).parent / old_doc.path
        if possible_path.exists():
            old_path = possible_path
            
    return link_supersession(old_path, new_path, version)
