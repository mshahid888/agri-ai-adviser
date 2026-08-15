"""Official agricultural source registry.

This module provides a deterministic, local registry of official agricultural
sources (extension departments, research institutes, laboratories, and official
publications) that the Agri-AI Adviser may later ingest.

The registry is stored as JSON files under ``knowledge/sources/registry/``.
Because the existing knowledge loader only scans ``.md`` and ``.txt`` files,
these JSON records are never loaded as knowledge documents and therefore do not
affect retrieval, scoring, orchestration, safety, or provenance logic.

The guiding principle is:

    OFFICIAL SOURCE -> CURATED/EXTRACTED KNOWLEDGE -> PROVENANCE -> RETRIEVER

This module is purely additive. It does not modify any existing module.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_DIR = PROJECT_ROOT / "knowledge" / "sources" / "registry"

REQUIRED_FIELDS = ("source_id", "title", "organization", "source_type", "status")


@dataclass
class SourceRecord:
    """Metadata record for a single official agricultural source."""

    source_id: str
    title: str
    organization: str
    source_type: str
    official_url: str = ""
    url_status: str = "pending_verification"
    document_path: str = ""
    crop: str = ""
    region: str = ""
    province: str = ""
    district: str = ""
    topic: str = ""
    publication_date: str = ""
    last_updated: str = ""
    version: str = ""
    evidence_quality: str = "general"
    status: str = "registered"
    notes: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "SourceRecord":
        return cls(
            source_id=str(data.get("source_id", "")),
            title=str(data.get("title", "")),
            organization=str(data.get("organization", "")),
            source_type=str(data.get("source_type", "")),
            official_url=str(data.get("official_url", "")),
            url_status=str(data.get("url_status", "pending_verification")),
            document_path=str(data.get("document_path", "")),
            crop=str(data.get("crop", "")),
            region=str(data.get("region", "")),
            province=str(data.get("province", "")),
            district=str(data.get("district", "")),
            topic=str(data.get("topic", "")),
            publication_date=str(data.get("publication_date", "")),
            last_updated=str(data.get("last_updated", "")),
            version=str(data.get("version", "")),
            evidence_quality=str(data.get("evidence_quality", "general")),
            status=str(data.get("status", "registered")),
            notes=str(data.get("notes", "")),
        )

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "title": self.title,
            "organization": self.organization,
            "source_type": self.source_type,
            "official_url": self.official_url,
            "url_status": self.url_status,
            "document_path": self.document_path,
            "crop": self.crop,
            "region": self.region,
            "province": self.province,
            "district": self.district,
            "topic": self.topic,
            "publication_date": self.publication_date,
            "last_updated": self.last_updated,
            "version": self.version,
            "evidence_quality": self.evidence_quality,
            "status": self.status,
            "notes": self.notes,
        }


def _registry_files() -> list[Path]:
    if not REGISTRY_DIR.exists():
        return []
    return sorted(path for path in REGISTRY_DIR.glob("*.json") if path.is_file())


def load_source_registry() -> list[SourceRecord]:
    """Load all source registry records from ``knowledge/sources/registry/``."""
    records: list[SourceRecord] = []
    for path in _registry_files():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(data, dict):
            records.append(SourceRecord.from_dict(data))
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    records.append(SourceRecord.from_dict(item))
    return records


def get_source(source_id: str) -> SourceRecord | None:
    """Return the source record with the given ``source_id`` or ``None``."""
    for record in load_source_registry():
        if record.source_id == source_id:
            return record
    return None


def list_sources() -> list[SourceRecord]:
    """Return all registered source records."""
    return load_source_registry()


def find_sources(**filters) -> list[SourceRecord]:
    """Return source records matching the given field filters.

    Example: ``find_sources(district="Sahiwal", status="registered")``
    """
    results = []
    for record in load_source_registry():
        matches = True
        for key, expected in filters.items():
            actual = getattr(record, key, None)
            if actual is None or str(actual) != str(expected):
                matches = False
                break
        if matches:
            results.append(record)
    return results


def validate_source_record(record: SourceRecord) -> list[str]:
    """Validate a source record and return a list of issues.

    An empty list means the record is valid.
    """
    issues: list[str] = []
    for field_name in REQUIRED_FIELDS:
        value = getattr(record, field_name, "")
        if not value or not str(value).strip():
            issues.append(f"Missing required field: {field_name}")

    if record.url_status == "verified" and not record.official_url.strip():
        issues.append("url_status is 'verified' but official_url is empty")

    if record.status not in {"registered", "ingested", "pending", "archived"}:
        issues.append(f"Unknown status: {record.status}")

    return issues


def register_document_path(source_id: str, document_path: str) -> str:
    """Register an original document path for a source record.

    This is an additive helper used by the M10 ingestion pipeline to link an
    ingested PDF to its source registry record.

    It will NOT silently overwrite an existing ``document_path``. If the source
    already has a ``document_path`` set, a ``ValueError`` is raised so the
    caller can handle the conflict explicitly and safely.

    The change is persisted to the source's registry JSON file.

    Returns the registered ``document_path`` on success.
    """
    if not document_path:
        raise ValueError("document_path must not be empty")

    record = get_source(source_id)
    if record is None:
        raise ValueError(f"Unknown source_id: {source_id}")

    if record.document_path:
        raise ValueError(
            f"Source '{source_id}' already has a document_path "
            f"('{record.document_path}'); refusing to overwrite it."
        )

    # Persist the change to the source's registry JSON file.
    filename = source_id.replace("-", "_") + ".json"
    path = REGISTRY_DIR / filename
    if not path.exists():
        raise ValueError(f"Registry file not found for source_id: {source_id}")

    data = json.loads(path.read_text(encoding="utf-8"))
    data["document_path"] = document_path
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    record.document_path = document_path
    return record.document_path
