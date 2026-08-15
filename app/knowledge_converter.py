"""Conversion of extracted PDF text into knowledge Markdown.

This module converts a ``PdfExtractionResult`` and ``DocumentMetadata`` into
curated knowledge Markdown that uses the existing front-matter architecture.
Extraction is verbatim: no paraphrasing, rewriting, or invented facts.

This module is strictly additive. It does not modify any existing module.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.document_metadata import DocumentMetadata
from app.pdf_extractor import PdfExtractionResult


@dataclass
class KnowledgeMarkdownOutput:
    """Output of converting extracted PDF text into knowledge Markdown."""

    markdown: str
    target_path: str


def _format_front_matter(metadata: DocumentMetadata) -> str:
    """Build YAML-style front matter from document metadata."""
    lines = [
        "---",
        f"title: {metadata.title}",
        f"crop: {metadata.crop}",
        f"region: {metadata.region}",
        f"province: {metadata.province}",
        f"district: {metadata.district}",
        f"topic: {metadata.topic}",
        f"source_type: {metadata.source_type}",
        f"evidence_quality: {metadata.evidence_quality}",
        f"version: {metadata.version}",
        f"last_updated: {metadata.last_updated}",
        f"status: {metadata.status}",
        f"source_id: {metadata.source_id}",
        f"document_id: {metadata.document_id}",
        f"original_pdf_path: {metadata.original_pdf_path}",
        "content_status: extracted",
        f"notes: {metadata.notes}",
        "---",
    ]
    return "\n".join(lines)


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
    ``document_id``.
    """
    front_matter = _format_front_matter(metadata)

    body_parts = [f"# {metadata.title}", ""]
    for page in extraction.pages:
        body_parts.append(f"<!-- Page {page.page_number} -->")
        page_text = _preserve_headings(page.text).strip()
        if page_text:
            body_parts.append(page_text)
        body_parts.append("")

    markdown = front_matter + "\n\n" + "\n".join(body_parts).rstrip() + "\n"
    return KnowledgeMarkdownOutput(markdown=markdown, target_path="")


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