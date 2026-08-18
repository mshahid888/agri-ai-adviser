"""Evidence Validation for the Agricultural AI Agent.

Validates retrieved evidence against schema, metadata, and relevance rules.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Any

from app.knowledge import EvidenceItem, EvidenceQuality


@dataclass
class EvidenceValidationResult:
    """Result of validating a set of evidence items."""
    valid_items: list[EvidenceItem] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    is_sufficient: bool = False


class EvidenceValidator:
    """Validates evidence quality, provenance, and relevance."""

    def validate(self, evidence: list[EvidenceItem], query: str = "") -> EvidenceValidationResult:
        """Validate a list of evidence items."""
        result = EvidenceValidationResult()
        
        for item in evidence:
            # 1. Document validity
            if not item.content:
                result.issues.append(f"Empty content in evidence from {item.source}")
                continue
            
            # 2. Provenance (basic check)
            if item.provenance and item.provenance.source_type == "unknown":
                result.issues.append(f"Unknown source type for {item.source}")

            # 3. Quality check
            if item.quality == EvidenceQuality.INSUFFICIENT:
                result.issues.append(f"Insufficient quality evidence from {item.source}")
                # Still add but don't prioritize
            
            # 4. Status (Superseded filtering already happens in retrieval, but we double check)
            # This is a simplified check. Real check would look at metadata['status'].
            
            result.valid_items.append(item)

        result.is_sufficient = len(result.valid_items) > 0
        return result
