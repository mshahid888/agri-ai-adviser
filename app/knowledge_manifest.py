"""Knowledge manifest for the Agri-AI Adviser.

This module provides a lightweight knowledge manifest/index that records
relevant metadata for knowledge documents, avoiding full-directory scans
when the manifest can answer the question.

The manifest tracks:
- document identity (document_id, path)
- source/provenance (source_id, source_type)
- version information
- content hash/checksum
- timestamps where already supported
- status (active, superseded, archived)
- relationships needed for supersession (supersedes)

The manifest is NOT the sole source of truth: existing knowledge loading
continues to work independently. The manifest is a performance optimization
and bookkeeping layer.

This module is strictly additive. It does not modify any existing module.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.knowledge import load_knowledge_documents, parse_front_matter

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST_PATH = PROJECT_ROOT / "knowledge" / "manifest.json"

MANIFEST_VERSION = "1.0"


@dataclass
class ManifestEntry:
    """Metadata record for a single knowledge document in the manifest."""

    document_id: str = ""
    path: str = ""
    title: str = ""
    source_id: str = ""
    source_type: str = ""
    version: str = ""
    status: str = "active"
    content_status: str = ""
    supersedes: str = ""
    evidence_quality: str = ""
    content_hash: str = ""
    last_updated: str = ""
    crop: str = ""
    region: str = ""
    province: str = ""
    district: str = ""
    farming_stage: str = ""
    organization: str = ""

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v}

    @classmethod
    def from_dict(cls, data: dict) -> ManifestEntry:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class KnowledgeManifest:
    """Knowledge manifest containing entries for all knowledge documents."""

    version: str = MANIFEST_VERSION
    entries: list[ManifestEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "entries": [entry.to_dict() for entry in self.entries],
        }

    @classmethod
    def from_dict(cls, data: dict) -> KnowledgeManifest:
        if not isinstance(data, dict):
            raise ValueError("Manifest data must be a dictionary")
        entries = []
        for entry_data in data.get("entries", []):
            if isinstance(entry_data, dict):
                entries.append(ManifestEntry.from_dict(entry_data))
        return cls(version=data.get("version", MANIFEST_VERSION), entries=entries)

    def get_entry(self, document_id: str) -> ManifestEntry | None:
        """Return the entry with the given document_id or None."""
        for entry in self.entries:
            if entry.document_id == document_id:
                return entry
        return None

    def get_entry_by_path(self, path: str) -> ManifestEntry | None:
        """Return the entry with the given path or None."""
        normalized = path.replace("\\", "/")
        for entry in self.entries:
            if entry.path.replace("\\", "/") == normalized:
                return entry
        return None

    def has_document(self, document_id: str) -> bool:
        return self.get_entry(document_id) is not None

    def has_path(self, path: str) -> bool:
        return self.get_entry_by_path(path) is not None


def compute_content_hash(content: str) -> str:
    """Compute a deterministic SHA-256 content hash."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def build_manifest_entry_from_document(doc: object) -> ManifestEntry:
    """Build a ManifestEntry from a KnowledgeDocument."""
    metadata = getattr(doc, "metadata", {}) or {}
    content = getattr(doc, "content", "")
    return ManifestEntry(
        document_id=metadata.get("document_id", ""),
        path=getattr(doc, "path", ""),
        title=getattr(doc, "title", ""),
        source_id=metadata.get("source_id", ""),
        source_type=metadata.get("source_type", ""),
        version=metadata.get("version", ""),
        status=metadata.get("status", "active"),
        content_status=metadata.get("content_status", ""),
        supersedes=metadata.get("supersedes", ""),
        evidence_quality=metadata.get("evidence_quality", ""),
        content_hash=compute_content_hash(content) if content else "",
        last_updated=metadata.get("last_updated", ""),
        crop=metadata.get("crop", ""),
        region=metadata.get("region", ""),
        province=metadata.get("province", ""),
        district=metadata.get("district", ""),
        farming_stage=metadata.get("farming_stage", ""),
        organization=metadata.get("organization", ""),
    )


def build_manifest_from_knowledge_base() -> KnowledgeManifest:
    """Build a manifest from the current knowledge base."""
    documents = load_knowledge_documents()
    manifest = KnowledgeManifest()
    for doc in documents:
        metadata = getattr(doc, "metadata", {}) or {}
        if not metadata:
            continue
        entry = build_manifest_entry_from_document(doc)
        manifest.entries.append(entry)
    return manifest


def load_manifest(path: str | Path | None = None) -> KnowledgeManifest:
    """Load a manifest from disk.

    Returns an empty manifest if the file doesn't exist or is corrupted.
    """
    manifest_path = Path(path) if path else DEFAULT_MANIFEST_PATH
    if not manifest_path.exists():
        return KnowledgeManifest()
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        return KnowledgeManifest.from_dict(data)
    except (json.JSONDecodeError, ValueError, KeyError):
        return KnowledgeManifest()


def save_manifest(manifest: KnowledgeManifest, path: str | Path | None = None) -> Path:
    """Save a manifest to disk."""
    manifest_path = Path(path) if path else DEFAULT_MANIFEST_PATH
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def compare_manifests(
    old: KnowledgeManifest,
    new: KnowledgeManifest,
) -> dict[str, list[ManifestEntry]]:
    """Compare two manifests and return added, removed, and changed entries.

    Returns a dict with keys: "added", "removed", "changed", "unchanged".
    """
    old_by_path = {entry.path.replace("\\", "/"): entry for entry in old.entries}
    new_by_path = {entry.path.replace("\\", "/"): entry for entry in new.entries}

    added = [entry for path, entry in new_by_path.items() if path not in old_by_path]
    removed = [entry for path, entry in old_by_path.items() if path not in new_by_path]

    changed = []
    unchanged = []
    for path, new_entry in new_by_path.items():
        if path in old_by_path:
            old_entry = old_by_path[path]
            if (
                new_entry.content_hash != old_entry.content_hash
                or new_entry.version != old_entry.version
                or new_entry.status != old_entry.status
            ):
                changed.append(new_entry)
            else:
                unchanged.append(new_entry)

    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "unchanged": unchanged,
    }
