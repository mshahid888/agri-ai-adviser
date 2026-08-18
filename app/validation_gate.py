"""Validation CI gate for the Agri-AI Adviser knowledge base.

This module provides automated validation that runs against all knowledge
documents and catches schema violations before changes can be accepted.

It reuses the existing knowledge schema validation from M11 and produces
useful failure messages identifying the invalid document and validation problem.

This module is strictly additive. It does not modify any existing module.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.knowledge import load_knowledge_documents
from app.knowledge_schema import (
    SchemaValidationResult,
    validate_knowledge_document,
)


@dataclass
class ValidationGateResult:
    """Result of running the validation gate against the knowledge base."""

    total_documents: int = 0
    valid_documents: int = 0
    invalid_documents: int = 0
    results: list[SchemaValidationResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Return True if all documents are valid."""
        return self.invalid_documents == 0

    @property
    def error_count(self) -> int:
        return sum(len(r.errors) for r in self.results)

    @property
    def warning_count(self) -> int:
        return sum(len(r.warnings) for r in self.results)

    def summary(self) -> str:
        """Return a human-readable summary of the validation gate result."""
        lines = [
            f"Validation Gate Result: {'PASS' if self.passed else 'FAIL'}",
            f"  Total documents: {self.total_documents}",
            f"  Valid: {self.valid_documents}",
            f"  Invalid: {self.invalid_documents}",
            f"  Errors: {self.error_count}",
            f"  Warnings: {self.warning_count}",
        ]
        if self.invalid_documents > 0:
            lines.append("")
            lines.append("Invalid documents:")
            for result in self.results:
                if not result.is_valid:
                    lines.append(f"  {result.document_path or '(unknown)'}:")
                    for error in result.errors:
                        lines.append(f"    ERROR: {error}")
        if self.warning_count > 0:
            lines.append("")
            lines.append("Warnings:")
            for result in self.results:
                for warning in result.warnings:
                    lines.append(f"  {result.document_path or '(unknown)'}: {warning}")
        return "\n".join(lines)


def run_validation_gate(
    knowledge_dir: str | Path | None = None,
) -> ValidationGateResult:
    """Run the validation gate against all knowledge documents.

    If ``knowledge_dir`` is provided, only documents under that directory
    are validated. Otherwise, all documents in the default knowledge
    directory are validated.

    Returns a ``ValidationGateResult`` with per-document results and
    aggregate counts.
    """
    documents = load_knowledge_documents()

    if knowledge_dir is not None:
        dir_str = str(knowledge_dir).replace("\\", "/").rstrip("/")
        documents = [doc for doc in documents if doc.path.replace("\\", "/").startswith(dir_str)]

    knowledge_documents = [doc for doc in documents if doc.metadata]

    gate_result = ValidationGateResult(total_documents=len(knowledge_documents))

    for doc in knowledge_documents:
        result = validate_knowledge_document(doc)
        gate_result.results.append(result)
        if result.is_valid:
            gate_result.valid_documents += 1
        else:
            gate_result.invalid_documents += 1

    return gate_result


def validate_knowledge_base() -> tuple[bool, str]:
    """Validate the entire knowledge base and return (passed, summary).

    This is a convenience function suitable for use as a CI check.
    Returns ``True`` if all documents pass validation, ``False`` otherwise.
    """
    gate_result = run_validation_gate()
    return gate_result.passed, gate_result.summary()
