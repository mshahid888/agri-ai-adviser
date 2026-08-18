"""Incremental ingestion for the Agri-AI Adviser.

This module builds incremental ingestion on top of the M12.2 manifest.
It detects new, modified, unchanged, and removed documents, and only
processes documents that actually require processing.

It uses the existing ingestion/extraction/schema/provenance pipeline
rather than creating a parallel ingestion system.

This module is strictly additive. It does not modify any existing module.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.ingestion import IngestionResult, ingest_pdf
from app.knowledge import load_knowledge_documents, parse_front_matter
from app.knowledge_manifest import (
    KnowledgeManifest,
    ManifestEntry,
    build_manifest_entry_from_document,
    build_manifest_from_knowledge_base,
    compute_content_hash,
    load_manifest,
    save_manifest,
)


@dataclass
class IncrementalIngestionResult:
    """Result of an incremental ingestion run."""

    new_documents: int = 0
    modified_documents: int = 0
    unchanged_documents: int = 0
    removed_documents: int = 0
    failed_documents: int = 0
    results: list[IngestionResult] = field(default_factory=list)
    manifest_before: KnowledgeManifest | None = None
    manifest_after: KnowledgeManifest | None = None

    @property
    def total_processed(self) -> int:
        return self.new_documents + self.modified_documents

    @property
    def success(self) -> bool:
        return self.failed_documents == 0


def detect_changes(manifest_path: str | Path | None = None) -> dict[str, list[ManifestEntry]]:
    """Detect changes between the stored manifest and the current knowledge base.

    Returns a dict with keys: "added", "removed", "changed", "unchanged".
    """
    old_manifest = load_manifest(manifest_path)
    new_manifest = build_manifest_from_knowledge_base()
    from app.knowledge_manifest import compare_manifests
    return compare_manifests(old_manifest, new_manifest)


def _build_target_manifest(target_dir: str | Path) -> KnowledgeManifest:
    """Build a manifest of documents currently in the target directory."""
    target = Path(target_dir)
    if not target.exists():
        return KnowledgeManifest()
    manifest = KnowledgeManifest()
    for md_path in sorted(target.rglob("*.md")):
        if not md_path.is_file():
            continue
        content = md_path.read_text(encoding="utf-8")
        metadata, body = parse_front_matter(content)
        if not metadata:
            continue
        rel = str(md_path).replace("\\", "/")
        entry = ManifestEntry(
            document_id=metadata.get("document_id", ""),
            path=rel,
            title=metadata.get("title", ""),
            source_id=metadata.get("source_id", ""),
            source_type=metadata.get("source_type", ""),
            version=metadata.get("version", ""),
            status=metadata.get("status", "active"),
            content_status=metadata.get("content_status", ""),
            supersedes=metadata.get("supersedes", ""),
            evidence_quality=metadata.get("evidence_quality", ""),
            content_hash=compute_content_hash(body),
            last_updated=metadata.get("last_updated", ""),
            crop=metadata.get("crop", ""),
            region=metadata.get("region", ""),
            province=metadata.get("province", ""),
            district=metadata.get("district", ""),
            farming_stage=metadata.get("farming_stage", ""),
            organization=metadata.get("organization", ""),
        )
        manifest.entries.append(entry)
    return manifest


def incremental_ingest(
    pdf_items: list[dict],
    target_dir: str | Path,
    manifest_path: str | Path | None = None,
) -> IncrementalIngestionResult:
    """Perform incremental ingestion of PDFs.

    Each item in ``pdf_items`` must be a dict with keys:
        pdf_path, source_id, document_id, title

    Only processes documents that are new (by document_id).
    Preserves existing full ingestion behavior for each document.

    Returns an ``IncrementalIngestionResult``.
    """
    old_manifest = load_manifest(manifest_path) if manifest_path else KnowledgeManifest()
    target_manifest = _build_target_manifest(target_dir)
    existing_doc_ids = {e.document_id for e in target_manifest.entries if e.document_id}

    result = IncrementalIngestionResult(manifest_before=old_manifest)

    for item in pdf_items:
        document_id = item.get("document_id", "")

        if document_id and document_id in existing_doc_ids:
            result.unchanged_documents += 1
            continue

        ingestion_result = ingest_pdf(
            pdf_path=item.get("pdf_path", ""),
            source_id=item.get("source_id", ""),
            document_id=document_id,
            title=item.get("title", ""),
            target_dir=target_dir,
            **{k: v for k, v in item.items() if k not in {"pdf_path", "source_id", "document_id", "title"}},
        )

        result.results.append(ingestion_result)
        if ingestion_result.success:
            if document_id and document_id not in existing_doc_ids:
                result.new_documents += 1
            else:
                result.modified_documents += 1
        else:
            result.failed_documents += 1

    if manifest_path:
        result.manifest_after = _build_target_manifest(target_dir)
        save_manifest(result.manifest_after, manifest_path)
    else:
        result.manifest_after = _build_target_manifest(target_dir)

    return result


def full_rebuild(
    pdf_items: list[dict],
    target_dir: str | Path,
    manifest_path: str | Path | None = None,
) -> IncrementalIngestionResult:
    """Perform a complete rebuild, ignoring the existing manifest.

    Processes all provided PDFs regardless of manifest state.
    Returns an ``IncrementalIngestionResult``.
    """
    result = IncrementalIngestionResult()

    for item in pdf_items:
        ingestion_result = ingest_pdf(
            pdf_path=item.get("pdf_path", ""),
            source_id=item.get("source_id", ""),
            document_id=item.get("document_id", ""),
            title=item.get("title", ""),
            target_dir=target_dir,
            **{k: v for k, v in item.items() if k not in {"pdf_path", "source_id", "document_id", "title"}},
        )
        result.results.append(ingestion_result)
        if ingestion_result.success:
            result.new_documents += 1
        else:
            result.failed_documents += 1

    if manifest_path:
        result.manifest_after = _build_target_manifest(target_dir)
        save_manifest(result.manifest_after, manifest_path)
    else:
        result.manifest_after = _build_target_manifest(target_dir)

    return result
