"""Safety Layer for the Agricultural AI Agent.

Provides deterministic validation of agricultural advice against high-risk patterns.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SafetyCheckResult:
    """Result of a safety validation check."""
    is_safe: bool = True
    violations: list[str] = field(default_factory=list)
    severity: str = "none"


HIGH_RISK_PATTERNS = {
    "pesticide_dose": r"\b(\d+(?:\.\d+)?)\s*(ml|cc|liter|l)/acre",
    "fertilizer_exact": r"\b(\d+(?:\.\d+)?)\s*(kg|bags?|tons?)\s*(per|/)\s*acre",
    "unauthorized_diagnosis": r"\bthis is.*?(disease|infection)\b",
    "unauthorized_variety": r"\b(plant|sow|use)\s+\w+[-\s]*\d+\b",
    "unauthorized_rate": r"\b(urea|dap|map)\s+(\d+)\s*(kg|bags?)",
}


class SafetyLayer:
    """Deterministic safety validator for agricultural advice."""

    def check(self, response_text: str) -> SafetyCheckResult:
        """Run all safety checks on the response text."""
        result = SafetyCheckResult()
        lower = response_text.lower()

        for check_name, pattern in HIGH_RISK_PATTERNS.items():
            if re.search(pattern, lower):
                result.violations.append(f"Safety violation: {check_name}")
                result.is_safe = False

        if result.violations:
            result.severity = "high"

        return result
