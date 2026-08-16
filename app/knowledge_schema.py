"""Production knowledge-document schema validation for the Agri-AI Adviser.

This module validates the front-matter metadata of knowledge Markdown files
against the production schema established in Milestone 11.

Validation is conditional on ``content_status``:

- placeholder: identity only; missing provenance is a warning, never fabricated
- extracted: source linkage and traceability required
- curated: source linkage, traceability, and review metadata required

It is strictly additive: it does not modify any existing module.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# ─── Schema definition ──────────────────────────────────────────────
#
# Field names match existing front-matter conventions in app/knowledge.py
# (DocumentProvenance, KnowledgeVersionInfo) and M10 ingestion output.

VALID_CONTENT_STATUSES: frozenset[str] = frozenset({
    "placeholder",
    "extracted",
    "curated",
})

VALID_SOURCE_TYPES: frozenset[str] = frozenset({
    "official_extension",
    "official_research_institute",
    "official_laboratory",
    "agricultural_guidance",
    "agricultural_context",
    "reference",
})

VALID_EVIDENCE_QUALITIES: frozenset[str] = frozenset({
    "insufficient",
    "general",
    "moderate",
    "strong",
})

VALID_STATUSES: frozenset[str] = frozenset({
    "active",
    "superseded",
    "archived",
    "ingested",
})

VALID_FARMING_STAGES: frozenset[str] = frozenset({
    "sowing_preparation",
    "nutrient_management",
    "irrigation",
    "pest_or_disease",
    "weed_management",
    "soil_management",
    "residue_management",
    "variety_selection",
    "general_crop_advice",
    "general",
    "",
})

# Always required regardless of content_status.
ALWAYS_REQUIRED: tuple[str, ...] = (
    "title",
    "content_status",
)

# Required for extracted and curated documents.
SOURCE_TRACE_REQUIRED: tuple[str, ...] = (
    "source_id",
    "document_id",
    "source_type",
    "version",
    "status",
    "evidence_quality",
)

# Additional provenance needed to trace an extracted document.
EXTRACTED_PROVENANCE_REQUIRED: tuple[str, ...] = (
    "organization",
)

# Review metadata required only for curated content.
CURATED_REVIEW_REQUIRED: tuple[str, ...] = (
    "reviewed_by",
    "review_date",
)

# Placeholder provenance: warn if absent; never require or invent.
PLACEHOLDER_PROVENANCE_OPTIONAL: tuple[str, ...] = (
    "source_id",
    "document_id",
    "source_type",
    "organization",
    "version",
)

# Accept existing aliases used by DocumentProvenance / KnowledgeVersionInfo.
FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "version": ("document_version",),
    "last_updated": ("last_modified",),
    "published_date": ("publication_date",),
}

DATE_FIELDS: tuple[str, ...] = (
    "last_updated",
    "last_modified",
    "published_date",
    "publication_date",
    "review_date",
)

ENUM_FIELDS: dict[str, frozenset[str]] = {
    "content_status": VALID_CONTENT_STATUSES,
    "source_type": VALID_SOURCE_TYPES,
    "evidence_quality": VALID_EVIDENCE_QUALITIES,
    "status": VALID_STATUSES,
    "farming_stage": VALID_FARMING_STAGES,
}

# At least one of these must be present on extracted/curated docs for traceability.
TRACE_DATE_OR_PATH_FIELDS: tuple[str, ...] = (
    "original_pdf_path",
    "last_updated",
    "last_modified",
    "published_date",
    "publication_date",
)


# ─── Result model ────────────────────────────────────────────────────


@dataclass
class SchemaValidationResult:
    """Result of validating knowledge document front matter."""

    document_path: str = ""
    is_valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def issues(self) -> list[str]:
        return self.errors + self.warnings


# ─── Validation helpers ─────────────────────────────────────────────

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SOURCE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _field_value(metadata: dict[str, str], field_name: str) -> str:
    """Return a stripped metadata value, honouring known aliases."""
    value = (metadata.get(field_name) or "").strip()
    if value:
        return value
    for alias in FIELD_ALIASES.get(field_name, ()):
        alias_value = (metadata.get(alias) or "").strip()
        if alias_value:
            return alias_value
    return ""


def _is_valid_date(value: str) -> bool:
    if not value:
        return True
    return bool(_DATE_RE.match(value))


def _is_valid_source_id_format(source_id: str) -> bool:
    return bool(_SOURCE_ID_RE.match(source_id))


def _require_fields(
    metadata: dict[str, str],
    field_names: tuple[str, ...],
    result: SchemaValidationResult,
) -> None:
    for field_name in field_names:
        if not _field_value(metadata, field_name):
            result.errors.append(f"Missing required field: {field_name}")


def _warn_missing_fields(
    metadata: dict[str, str],
    field_names: tuple[str, ...],
    result: SchemaValidationResult,
) -> None:
    for field_name in field_names:
        if not _field_value(metadata, field_name):
            result.warnings.append(f"Missing recommended field: {field_name}")


def _lookup_source(source_id: str) -> Any | None:
    """Look up a source_id in the M9 registry. Returns None if unknown."""
    try:
        from app.source_registry import get_source
    except ImportError:
        return None
    return get_source(source_id)


# ─── Public API ─────────────────────────────────────────────────────


def validate_knowledge_metadata(
    metadata: dict[str, str],
    document_path: str = "",
) -> SchemaValidationResult:
    """Validate knowledge-document front-matter metadata against the production schema.

    Returns a ``SchemaValidationResult`` with:
    - ``errors``: blocking issues (missing required fields, invalid enums, bad dates)
    - ``warnings``: non-blocking issues (missing recommended provenance, odd combinations)
    """
    result = SchemaValidationResult(document_path=document_path, is_valid=True)

    _require_fields(metadata, ALWAYS_REQUIRED, result)

    content_status = _field_value(metadata, "content_status")

    if content_status == "placeholder":
        _warn_missing_fields(metadata, PLACEHOLDER_PROVENANCE_OPTIONAL, result)
    elif content_status == "extracted":
        _require_fields(metadata, SOURCE_TRACE_REQUIRED, result)
        _require_fields(metadata, EXTRACTED_PROVENANCE_REQUIRED, result)
        if not any(_field_value(metadata, name) for name in TRACE_DATE_OR_PATH_FIELDS):
            result.errors.append(
                "Extracted document needs at least one of: original_pdf_path, "
                "last_updated, published_date."
            )
    elif content_status == "curated":
        _require_fields(metadata, SOURCE_TRACE_REQUIRED, result)
        _require_fields(metadata, EXTRACTED_PROVENANCE_REQUIRED, result)
        _require_fields(metadata, CURATED_REVIEW_REQUIRED, result)
        if not any(_field_value(metadata, name) for name in TRACE_DATE_OR_PATH_FIELDS):
            result.errors.append(
                "Curated document needs at least one of: original_pdf_path, "
                "last_updated, published_date."
            )

    for field_name, valid_values in ENUM_FIELDS.items():
        value = _field_value(metadata, field_name)
        if value and value not in valid_values:
            display = ", ".join(sorted(v for v in valid_values if v))
            result.errors.append(
                f"Invalid value for {field_name}: '{value}'. Valid: {display}"
            )

    for field_name in DATE_FIELDS:
        value = (metadata.get(field_name) or "").strip()
        if value and not _is_valid_date(value):
            result.errors.append(
                f"Invalid date for {field_name}: '{value}'. Expected YYYY-MM-DD."
            )

    status = _field_value(metadata, "status")
    supersedes = _field_value(metadata, "supersedes")

    if status == "superseded" and supersedes:
        result.warnings.append(
            "Document status is 'superseded' but 'supersedes' is set; "
            "'supersedes' means this document replaces an older version."
        )

    if status == "archived" and supersedes:
        result.warnings.append(
            "Document is 'archived' but 'supersedes' is set; "
            "archived documents should not replace other versions."
        )

    source_id = _field_value(metadata, "source_id")
    if source_id:
        if not _is_valid_source_id_format(source_id):
            result.errors.append(
                f"Invalid source_id format: '{source_id}'. "
                "Expected lowercase alphanumeric with hyphens."
            )
        elif _lookup_source(source_id) is None:
            result.errors.append(f"Unknown source_id: {source_id}")

    result.is_valid = len(result.errors) == 0
    return result


def validate_knowledge_document(document: Any) -> SchemaValidationResult:
    """Validate a ``KnowledgeDocument`` (from ``app.knowledge``) against the schema."""
    metadata = dict(getattr(document, "metadata", {}) or {})
    if not _field_value(metadata, "title"):
        title = getattr(document, "title", "") or ""
        if title:
            metadata["title"] = title
    return validate_knowledge_metadata(
        metadata,
        document_path=getattr(document, "path", ""),
    )


def validate_all_knowledge_documents(documents: list[Any]) -> list[SchemaValidationResult]:
    """Validate a list of knowledge documents and return results for each."""
    return [validate_knowledge_document(doc) for doc in documents]
