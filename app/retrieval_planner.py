"""Retrieval Planner for the Agricultural AI Agent.

Formulates evidence retrieval strategies based on user query, intent,
and farmer context to ensure relevant, high-precision results.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.adviser import AgriculturalIntent, RiskLevel, determine_risk_level
from app.farmer_context import FarmerContext
from app.intent_classifier import IntentClassificationResult


@dataclass
class RetrievalPlan:
    """Strategy and parameters for hybrid evidence retrieval."""

    query: str
    intent: AgriculturalIntent
    risk_level: RiskLevel
    top_k: int = 3
    use_semantic: bool = True
    use_heuristic: bool = True
    metadata_filters: dict[str, str] = field(default_factory=dict)
    reason: str = ""


class RetrievalPlanner:
    """Generates optimal retrieval strategies based on structured inputs."""

    def plan(
        self,
        query: str,
        classification: IntentClassificationResult,
        context: Optional[FarmerContext] = None,
    ) -> RetrievalPlan:
        """Formulate a retrieval plan."""
        intent = classification.intent
        risk_level = determine_risk_level(intent)
        
        # Build metadata filters based on context and entities
        filters = {}
        if context:
            if context.crop:
                filters["crop"] = context.crop.lower()
            if context.province:
                filters["province"] = context.province.lower()
            if context.district:
                filters["district"] = context.district.lower()

        # Merge extracted entities from classification
        for key, value in classification.entities.items():
            filters[key] = value.lower()

        # Decide retrieval strategy
        use_semantic = True
        use_heuristic = True
        reason = "Using hybrid retrieval by default for maximum precision."

        # If intent confidence is extremely low, fallback to broad search
        if classification.confidence < 0.3:
            use_semantic = True
            use_heuristic = True
            reason = "Low intent confidence; initiating broad hybrid search."

        # High risk items require more evidence
        top_k = 3
        if risk_level == RiskLevel.HIGH:
            top_k = 5
            reason += " High-risk intent detected; expanding candidate search size."

        return RetrievalPlan(
            query=query,
            intent=intent,
            risk_level=risk_level,
            top_k=top_k,
            use_semantic=use_semantic,
            use_heuristic=use_heuristic,
            metadata_filters=filters,
            reason=reason,
        )
