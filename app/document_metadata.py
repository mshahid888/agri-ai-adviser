"""Document metadata association for the Agri-AI Adviser.

This module builds and validates metadata for ingested PDF documents,
linking them to the M9 source registry via ``source_id``.

This module is strictly additive. It does not modify any existing module.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.source_registry import get_source


@dataclass
class DocumentMetadata:
    """Metadata for an ingested PDF document, linked to a source registry record."""

    source_id: str
    document_id: str
    title: str
    original_pdf_path: str
    crop: str = ""
    region: str = ""
    province: str = ""
    district: str = ""
    topic: str = ""
    source_type: str = ""
    evidence_quality: str = "general"
    version: str = ""
    last_updated: str = ""
    status: str = "ingested"
    notes: str = ""


def build_document_metadata(
    source_id: str,
    document_id: str,
    title: str,
    original_pdf_path: str,
    **overrides,
) -> DocumentMetadata:
    """Build a ``DocumentMetadata`` linked to the given ``source_id``.

    The ``source_id`` must exist in the M9 source registry. If it does not,
    a ``ValueError`` is raised.
    """
    source = get_source(source_id)
    if source is None:
        raise ValueError(f"Unknown source_id: {source_id}")

    metadata = DocumentMetadata(
        source_id=source_id,
        document_id=document_id,
        title=title,
        original_pdf_path=original_pdf_path,
        crop=source.crop,
        region=source.region,
        province=source.province,
        district=source.district,
        topic=source.topic,
        source_type=source.source_type,
        evidence_quality=source.evidence_quality,
        version=source.version,
        last_updated=source.last_updated,
        status="ingested",
        notes=source.notes,
    )

    for key, value in overrides.items():
        if hasattr(metadata, key):
            setattr(metadata, key, value)

    return metadata


def validate_document_metadata(metadata: DocumentMetadata) -> list[str]:
    """Validate a ``DocumentMetadata`` and return a list of issues.

    An empty list means the metadata is valid.
    """
    issues: list[str] = []

    if not metadata.source_id:
        issues.append("Missing required field: source_id")
    if not metadata.document_id:
        issues.append("Missing required field: document_id")
    if not metadata.title:
        issues.append("Missing required field: title")
    if not metadata.original_pdf_path:
        issues.append("Missing required field: original_pdf_path")

    if metadata.source_id and get_source(metadata.source_id) is None:
        issues.append(f"Unknown source_id: {metadata.source_id}")

    return issues