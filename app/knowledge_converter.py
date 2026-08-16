"""Conversion of extracted PDF text into knowledge Markdown.

This module converts a ``PdfExtractionResult`` and ``DocumentMetadata`` into
curated knowledge Markdown that uses the existing front-matter architecture.
Extraction is verbatim: no paraphrasing, rewriting, or invented facts.

This module is strictly additive. It does not modify any existing module.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.document_metadata import DocumentMetadata
from app.pdf_extractor import PdfExtractionResult
from app.knowledge_schema import validate_knowledge_metadata

@dataclass
class KnowledgeMarkdownOutput:
    """Output of converting extracted PDF text into knowledge Markdown."""
    markdown: str
    target_path: str
    metadata: dict[str, str] = field(default_factory=dict)



def _format_front_matter(metadata: DocumentMetadata) -> tuple[str, dict[str, str]]:
    """Build YAML-style front matter from document metadata."""
    metadata_dict = {
        "title": metadata.title,
        "crop": metadata.crop,
        "region": metadata.region,
        "province": metadata.province,
        "district": metadata.district,
        "topic": metadata.topic,
        "source_type": metadata.source_type,
        "evidence_quality": metadata.evidence_quality,
        "version": metadata.version,
        "last_updated": metadata.last_updated,
        "status": metadata.status,
        "source_id": metadata.source_id,
        "document_id": metadata.document_id,
        "original_pdf_path": metadata.original_pdf_path,
        "content_status": "extracted",
        "notes": metadata.notes,
        "organization": metadata.organization,
    }

    lines = ["---"]
    for key, value in metadata_dict.items():
        lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines), metadata_dict


def _preserve_headings(text: str) -> str:
    """Heuristically preserve markdown-style headings in extracted text.

    Lines that already look like markdown headings (``#``, ``##``, etc.) are
    kept as-is. No structure is fabricated.
    """
    lines = text.splitlines()
    preserved = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            preserved.append(stripped)
        else:
            preserved.append(line)
    return "\n".join(preserved)


def convert_to_knowledge_markdown(
    extraction: PdfExtractionResult,
    metadata: DocumentMetadata,
) -> KnowledgeMarkdownOutput:
    """Convert extracted PDF text into knowledge Markdown.

    The body preserves page boundaries and detected headings. The front matter
    links the document to the M9 source registry via ``source_id`` and
    ``document_id``. Includes schema validation to ensure valid output.
    """
    front_matter, metadata_dict = _format_front_matter(metadata)

    # Validate against production schema
    validation = validate_knowledge_metadata(metadata_dict)
    if not validation.is_valid:
        raise ValueError(f"Generated metadata fails schema validation: {validation.errors}")

    body_parts = [f"# {metadata.title}", ""]
    for page in extraction.pages:
        body_parts.append(f"<!-- Page {page.page_number} -->")
        page_text = _preserve_headings(page.text).strip()
        if page_text:
            body_parts.append(page_text)
        body_parts.append("")

    markdown = front_matter + "\n\n" + "\n".join(body_parts).rstrip() + "\n"
    return KnowledgeMarkdownOutput(markdown=markdown, target_path="", metadata=metadata_dict)


def write_knowledge_markdown(
    output: KnowledgeMarkdownOutput,
    target_dir: str | Path,
    filename: str,
) -> str:
    """Write the knowledge Markdown to ``target_dir / filename``.

    Returns the written file path as a string.
    """
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)
    path = target / filename
    path.write_text(output.markdown, encoding="utf-8")
    output.target_path = str(path)
    return str(path)