"""
Milestone 12 tests: Intent Classifier.

Tests verify intent classification:
- deterministic behavior
- farming stage identification
- crop and geographic applicability detection
- query intent extraction
- graceful degradation
- backward compatibility
"""
from app.adviser import AgriculturalIntent
from app.farmer_context import FarmerContext
from app.intent_classifier import (
    IntentClassificationResult,
    IntelligentIntentClassifier,
    intelligent_classify_intent,
)


# ─── Deterministic behavior ─────────────────────────────────────────────────

def test_classify_returns_consistent_results():
    classifier = IntelligentIntentClassifier()
    result1 = classifier.classify("When should I sow wheat?")
    result2 = classifier.classify("When should I sow wheat?")
    assert result1.intent == result2.intent
    assert result1.confidence == result2.confidence


def test_classify_empty_query_returns_unknown():
    classifier = IntelligentIntentClassifier()
    result = classifier.classify("")
    assert result.intent == AgriculturalIntent.UNKNOWN
    assert result.confidence == 0.0


def test_classify_none_query_returns_unknown():
    classifier = IntelligentIntentClassifier()
    result = classifier.classify(None)
    assert result.intent == AgriculturalIntent.UNKNOWN


# ─── Farming stage identification ───────────────────────────────────────────

def test_classify_sowing_intent():
    result = intelligent_classify_intent("When should I sow wheat in Punjab?")
    assert result.intent == AgriculturalIntent.SOWING_PREPARATION
    assert "sow" in result.matched_keywords


def test_classify_irrigation_intent():
    result = intelligent_classify_intent("How often should I irrigate my rice crop?")
    assert result.intent == AgriculturalIntent.IRRIGATION
    assert "irrigate" in result.matched_keywords


def test_classify_fertilizer_intent():
    result = intelligent_classify_intent("What fertilizer should I apply to wheat?")
    assert result.intent == AgriculturalIntent.NUTRIENT_MANAGEMENT


def test_classify_pest_disease_intent():
    result = intelligent_classify_intent("My wheat has yellow leaves, what should I spray?")
    assert result.intent == AgriculturalIntent.PEST_OR_DISEASE


def test_classify_weed_management_intent():
    result = intelligent_classify_intent("How do I control weeds in my rice field?")
    assert result.intent == AgriculturalIntent.WEED_MANAGEMENT


def test_classify_variety_selection_intent():
    result = intelligent_classify_intent("Which wheat variety should I plant in Sahiwal?")
    assert result.intent == AgriculturalIntent.VARIETY_SELECTION


# ─── Crop detection ──────────────────────────────────────────────────────────

def test_classify_extracts_wheat_crop():
    result = intelligent_classify_intent("I need advice for my wheat crop")
    assert result.entities.get("crop") == "Wheat"


def test_classify_extracts_rice_crop():
    result = intelligent_classify_intent("How to irrigate rice in Punjab?")
    assert result.entities.get("crop") == "Rice"


def test_classify_extracts_maize_crop():
    result = intelligent_classify_intent("Best fertilizer for maize?")
    assert result.entities.get("crop") == "Maize"


# ─── Geographic applicability ────────────────────────────────────────────────

def test_classify_extracts_location_sahiwal():
    result = intelligent_classify_intent("When to sow wheat in Sahiwal district?")
    assert result.entities.get("location") == "Sahiwal"


def test_classify_extracts_location_punjab():
    result = intelligent_classify_intent("What varieties are best for Punjab?")
    assert result.entities.get("location") == "Punjab"


# ─── Context integration ─────────────────────────────────────────────────────

def test_classify_uses_context_crop():
    context = FarmerContext(crop="Wheat", country="Pakistan")
    result = intelligent_classify_intent("What fertilizer to apply?", context)
    assert result.entities.get("crop") == "Wheat"


def test_classify_uses_context_problem():
    context = FarmerContext(crop="Wheat", country="Pakistan", problem="yellow leaves")
    result = intelligent_classify_intent("What should I do?", context)
    assert result.intent == AgriculturalIntent.PEST_OR_DISEASE
    assert "yellow" in result.matched_keywords


# ─── Graceful degradation ────────────────────────────────────────────────────

def test_classify_unknown_intent_for_unrelated_query():
    result = intelligent_classify_intent("What is the capital of France?")
    assert result.intent in {AgriculturalIntent.UNKNOWN, AgriculturalIntent.GENERAL_CROP_ADVICE}
    assert result.is_valid is False or result.intent == AgriculturalIntent.GENERAL_CROP_ADVICE


def test_classify_low_confidence_for_ambiguous_query():
    result = intelligent_classify_intent("I have a problem")
    assert result.confidence < 0.5


# ─── IntentClassificationResult dataclass ────────────────────────────────────

def test_intent_classification_result_defaults():
    result = IntentClassificationResult(intent=AgriculturalIntent.UNKNOWN, confidence=0.5)
    assert result.confidence == 0.5
    assert result.matched_keywords == []
    assert result.entities == {}
    assert result.is_valid is True
    assert result.issues == []


# ─── Backward compatibility ─────────────────────────────────────────────────

def test_intent_classifier_does_not_break_legacy():
    from app.adviser import classify_agricultural_intent
    farmer = FarmerContext(crop="Wheat", country="Pakistan")

    legacy = classify_agricultural_intent("When should I sow wheat?", farmer)
    new = intelligent_classify_intent("When should I sow wheat?", farmer)

    assert legacy == AgriculturalIntent.SOWING_PREPARATION
    assert new.intent == AgriculturalIntent.SOWING_PREPARATION


# ─── Confidence bounds ───────────────────────────────────────────────────────

def test_confidence_is_bounded():
    classifier = IntelligentIntentClassifier()
    result = classifier.classify("sow sow sow sow sow sow sow sow")
    assert 0.0 <= result.confidence <= 1.0


# ─── Keyword matching ────────────────────────────────────────────────────────

def test_matched_keywords_populated():
    result = intelligent_classify_intent("I need advice on sowing wheat and irrigation")
    assert len(result.matched_keywords) > 0
