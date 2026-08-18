"""Intent classification layer for natural-language agricultural queries.

This module provides deterministic, pattern-based, and semantic-boosted
intent classification that integrates with the existing retrieval and
orchestration pipelines.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.adviser import AgriculturalIntent, classify_agricultural_intent
from app.farmer_context import FarmerContext


@dataclass
class IntentClassificationResult:
    """Structured result of intent classification."""

    intent: AgriculturalIntent
    confidence: float  # 0.0 to 1.0
    matched_keywords: list[str] = field(default_factory=list)
    entities: dict[str, str] = field(default_factory=dict)  # extracted crop, location, etc.
    is_valid: bool = True
    issues: list[str] = field(default_factory=list)


class IntelligentIntentClassifier:
    """Deterministic and heuristic intent classifier for agricultural queries."""

    INTENT_KEYWORDS: dict[AgriculturalIntent, list[str]] = {
        AgriculturalIntent.SOWING_PREPARATION: [
            "sow", "sowing", "planting", "seedbed", "when to sow", "plant date", "sowing date",
            "germination", "seed rate", "seed treatment"
        ],
        AgriculturalIntent.NUTRIENT_MANAGEMENT: [
            "fertilizer", "dap", "urea", "nutrient", "nitrogen", "phosphorus", "potassium",
            "npk", "manure", "zinc", "gypsum", "soil test"
        ],
        AgriculturalIntent.IRRIGATION: [
            "irrigation", "irrigate", "water", "moisture", "when to irrigate", "watering", "canal", "tubewell",
            "dryness", "drought", "irrigated", "irrigating"
        ],
        AgriculturalIntent.PEST_OR_DISEASE: [
            "pesticide", "spray", "herbicide", "fungicide", "yellow leaves", "yellow", "disease",
            "wilt", "rust", "leaf spot", "powdery mildew", "yellowing", "chlorosis", "insect", "bug",
            "pest", "aphid", "blight", "spots"
        ],
        AgriculturalIntent.WEED_MANAGEMENT: [
            "weed", "weeds", "herbicide", "weed control", "spraying weed", "convolvulus", "wild oat"
        ],
        AgriculturalIntent.SOIL_MANAGEMENT: [
            "soil", "texture", "salinity", "structure", "loam", "clay", "sandy", "silt", "saline",
            "ph level", "acidic", "alkaline"
        ],
        AgriculturalIntent.RESIDUE_MANAGEMENT: [
            "residue", "straw", "rice straw", "burning residue", "residue management", "burning", "mulch"
        ],
        AgriculturalIntent.VARIETY_SELECTION: [
            "variety", "cultivar", "seed variety", "which variety", "yield potential", "akbar", "dilkash",
            "bakar", "subhani"
        ],
        AgriculturalIntent.GENERAL_CROP_ADVICE: [
            "advice", "help", "what should i do", "management", "recommendation", "crop cycle",
            "weather impact", "temperature"
        ],
    }

    def classify(self, query: str | None, context: FarmerContext | None = None) -> IntentClassificationResult:
        """Classify a query with high precision, validating result constraints."""
        text = (query or "").lower().strip()
        context_text = ""
        if context:
            context_text = " ".join(filter(None, [context.crop, context.problem, context.previous_crop])).lower()
        
        # Combine query and context for keyword matching
        scoring_text = f"{text} {context_text}".strip()
        
        if not scoring_text and context:
            scoring_text = context_text

        if not scoring_text:
            return IntentClassificationResult(
                intent=AgriculturalIntent.UNKNOWN,
                confidence=0.0,
                issues=["Empty query and no context available"],
            )

        # 1. Base legacy classification for fallback comparison
        legacy_intent = classify_agricultural_intent(query, context)

        # 2. Key-based heuristic scoring using combined text
        scores: dict[AgriculturalIntent, int] = {}
        matched_words: dict[AgriculturalIntent, list[str]] = {}

        for intent, keywords in self.INTENT_KEYWORDS.items():
            scores[intent] = 0
            matched_words[intent] = []
            for word in keywords:
                if re.search(r"\b" + re.escape(word) + r"\b", scoring_text):
                    scores[intent] += 3
                    matched_words[intent].append(word)
                elif word in scoring_text:
                    scores[intent] += 1
                    matched_words[intent].append(word)

        # Determine winner
        best_intent = AgriculturalIntent.UNKNOWN
        best_score = 0
        best_matches: list[str] = []

        for intent, score in scores.items():
            if score > best_score:
                best_score = score
                best_intent = intent
                best_matches = matched_words[intent]

        # Map score to confidence percentage
        confidence = 0.0
        if best_score > 0:
            # simple formula to bound confidence between 0.3 and 0.95
            confidence = min(0.3 + (best_score * 0.1), 0.95)
        else:
            # Fallback to legacy
            best_intent = legacy_intent
            confidence = 0.3 if legacy_intent != AgriculturalIntent.UNKNOWN else 0.0

        # Extract entities deterministically
        entities = {}
        crop_match = re.search(r"\b(wheat|rice|maize|cotton|sugarcane|potato)\b", text)
        if crop_match:
            entities["crop"] = crop_match.group(1).title()
        elif context and context.crop:
            entities["crop"] = context.crop

        location_markers = ["sahiwal", "lahore", "multan", "punjab", "pakistan"]
        for loc in location_markers:
            if loc in text:
                entities["location"] = loc.title()
                break

        # Validate the output
        issues = []
        is_valid = True
        if best_intent == AgriculturalIntent.UNKNOWN and text:
            issues.append("Unable to determine a specific intent category")
            is_valid = False

        return IntentClassificationResult(
            intent=best_intent,
            confidence=confidence,
            matched_keywords=best_matches,
            entities=entities,
            is_valid=is_valid,
            issues=issues,
        )


def intelligent_classify_intent(query: str | None, context: FarmerContext | None = None) -> IntentClassificationResult:
    """Helper convenience function to classify query intent."""
    return IntelligentIntentClassifier().classify(query, context)
