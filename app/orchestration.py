from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from app.adviser import (
    AgriculturalCase,
    AgriculturalIntent,
    AgriculturalResponse,
    RiskLevel,
    ask_adviser,
    build_decision_plan,
    classify_agricultural_intent,
    validate_response_detailed,
)
from app.farmer_context import FarmerContext
from app.knowledge import LocalKnowledgeRetriever, detect_conflicts


@dataclass
class FarmerQueryInput:
    raw_text: str
    context: Optional[FarmerContext] = None
    conversation_history: Optional[list[str]] = None
    language: Optional[str] = None
    urgency: Optional[str] = None


@dataclass
class NormalizedFarmerRequest:
    crop: Optional[str] = None
    country: Optional[str] = None
    province: Optional[str] = None
    district: Optional[str] = None
    previous_crop: Optional[str] = None
    soil_type: Optional[str] = None
    irrigation: Optional[str] = None
    sowing_date: Optional[str] = None
    growth_stage: Optional[str] = None
    problem: Optional[str] = None
    observations: Optional[str] = None
    machinery: Optional[str] = None
    farmer_question: Optional[str] = None


@dataclass
class ClarificationResult:
    missing_information: list[str]
    why_it_matters: str
    follow_up_questions: list[str]
    safe_general_guidance: list[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class EvidenceBundle:
    evidence_items: list[Any] = field(default_factory=list)
    source_paths: list[str] = field(default_factory=list)
    provenance: list[Any] = field(default_factory=list)
    versions: list[str] = field(default_factory=list)
    conflicts: list[Any] = field(default_factory=list)
    quality_summary: dict[str, Any] = field(default_factory=dict)
    local_specificity: str = "general"
    evidence_available: bool = False


@dataclass
class OrchestrationOutcome:
    is_clarification_required: bool
    clarification: Optional[ClarificationResult] = None
    response: Optional[AgriculturalResponse] = None


def _normalize_single_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _extract_country_from_text(text: str) -> Optional[str]:
    lower = text.lower()
    if "pakistan" in lower:
        return "Pakistan"
    if "india" in lower:
        return "India"
    return None


def _extract_province_from_text(text: str) -> Optional[str]:
    lower = text.lower()
    if "punjab" in lower:
        return "Punjab"
    if "sindh" in lower:
        return "Sindh"
    if "balochistan" in lower:
        return "Balochistan"
    if "khyber" in lower or "kpk" in lower:
        return "Khyber Pakhtunkhwa"
    return None


def _extract_district_from_text(text: str) -> Optional[str]:
    lower = text.lower()
    districts = ["sahiwal", "lahore", "multan", "gujranwala", "faisalabad", "bahawalpur"]
    for district in districts:
        if district in lower:
            return district.title()
    return None


def _extract_crop_from_text(text: str) -> Optional[str]:
    lower = text.lower()
    crops = ["wheat", "rice", "maize", "cotton", "sugarcane"]
    for crop in crops:
        if crop in lower:
            return crop.title()
    return None


def _extract_previous_crop_from_text(text: str) -> Optional[str]:
    lower = text.lower()
    patterns = [
        r"last crop was\s+([a-z]+)",
        r"previous crop was\s+([a-z]+)",
        r"previously\s+([a-z]+)",
        r"after\s+([a-z]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, lower)
        if match:
            candidate = match.group(1).strip()
            for crop in ["rice", "wheat", "maize", "cotton"]:
                if candidate == crop:
                    return crop.title()
    if "previous crop" in lower:
        idx = lower.find("previous crop")
        rest = lower[idx + len("previous crop") :]
        for crop in ["rice", "wheat", "maize", "cotton"]:
            if crop in rest:
                return crop.title()
    return None


def _extract_soil_type_from_text(text: str) -> Optional[str]:
    lower = text.lower()
    soil_types = ["loam", "clay", "sandy", "silty", "saline"]
    for soil_type in soil_types:
        if soil_type in lower:
            return soil_type.title()
    return None


def _extract_planting_indicators(text: str) -> Optional[str]:
    lower = text.lower()
    if "seedbed" in lower:
        return "seedbed preparation"
    if "sow" in lower or "planting" in lower:
        return "sowing"
    return None


def _infer_problem_from_text(text: str) -> Optional[str]:
    lower = text.lower()
    problem_markers = [
        "seedbed",
        "sow",
        "plant",
        "yellow",
        "rust",
        "pesticide",
        "spray",
        "fertilizer",
        "urea",
        "insecticide",
        "symptoms",
    ]
    for marker in problem_markers:
        if marker in lower:
            return text.strip()
    return None


def normalize_farmer_query(query: FarmerQueryInput) -> NormalizedFarmerRequest:
    raw_text = query.raw_text or ""
    text = raw_text.strip()

    normalized = NormalizedFarmerRequest()

    context = query.context
    if context:
        normalized.crop = _normalize_single_value(context.crop)
        normalized.country = _normalize_single_value(context.country)
        normalized.province = _normalize_single_value(context.province)
        normalized.district = _normalize_single_value(context.district)
        normalized.previous_crop = _normalize_single_value(context.previous_crop)
        normalized.soil_type = _normalize_single_value(context.soil_type)
        normalized.irrigation = _normalize_single_value(context.irrigation)
        normalized.sowing_date = _normalize_single_value(context.sowing_date)
        normalized.growth_stage = _normalize_single_value(context.growth_stage)
        normalized.problem = _normalize_single_value(context.problem)

    if text:
        if not normalized.crop:
            normalized.crop = _extract_crop_from_text(text)
        if not normalized.country:
            normalized.country = _extract_country_from_text(text)
        if not normalized.province:
            normalized.province = _extract_province_from_text(text)
        if not normalized.district:
            normalized.district = _extract_district_from_text(text)
        if not normalized.previous_crop:
            normalized.previous_crop = _extract_previous_crop_from_text(text)
        if not normalized.soil_type:
            normalized.soil_type = _extract_soil_type_from_text(text)
        if not normalized.problem:
            normalized.problem = _infer_problem_from_text(text)

    if context and context.problem and not normalized.farmer_question:
        normalized.farmer_question = context.problem
    elif text:
        normalized.farmer_question = text

    if not normalized.problem and text:
        normalized.problem = text

    if normalized.crop and normalized.farmer_question and normalized.farmer_question.lower().startswith(normalized.crop.lower()):
        normalized.farmer_question = normalized.farmer_question.strip()

    return normalized


def _determine_risk(intent: AgriculturalIntent, normalized: NormalizedFarmerRequest) -> RiskLevel:
    if intent in {AgriculturalIntent.SOWING_PREPARATION, AgriculturalIntent.GENERAL_CROP_ADVICE, AgriculturalIntent.RESIDUE_MANAGEMENT}:
        return RiskLevel.LOW
    if intent in {AgriculturalIntent.NUTRIENT_MANAGEMENT, AgriculturalIntent.IRRIGATION, AgriculturalIntent.SOIL_MANAGEMENT, AgriculturalIntent.WEED_MANAGEMENT, AgriculturalIntent.VARIETY_SELECTION}:
        return RiskLevel.MODERATE
    if intent == AgriculturalIntent.PEST_OR_DISEASE:
        text = (normalized.farmer_question or normalized.problem or "").lower()
        if any(keyword in text for keyword in ["pesticide", "spray", "dose", "per acre", "chemical", "treat"]) or normalized.growth_stage:
            return RiskLevel.HIGH
        return RiskLevel.HIGH
    return RiskLevel.MODERATE


def _build_missing_information_rules(intent: AgriculturalIntent, normalized: NormalizedFarmerRequest) -> dict[str, Any]:
    required = []
    optional = []

    if intent == AgriculturalIntent.SOWING_PREPARATION:
        required = ["crop"]
        optional = ["country", "province", "district", "previous_crop", "soil_type", "sowing_date", "problem"]
    elif intent == AgriculturalIntent.NUTRIENT_MANAGEMENT:
        required = ["crop", "soil_type"]
        optional = ["country", "province", "district", "previous_crop", "sowing_date", "problem"]
    elif intent == AgriculturalIntent.PEST_OR_DISEASE:
        required = ["crop", "problem"]
        optional = ["growth_stage", "province", "district", "soil_type", "observations"]
    elif intent == AgriculturalIntent.VARIETY_SELECTION:
        required = ["crop"]
        optional = ["country", "province", "district", "previous_crop", "soil_type", "sowing_date"]
    else:
        required = ["crop"]
        optional = ["country", "province", "district", "problem"]

    values = {
        "crop": normalized.crop,
        "country": normalized.country,
        "province": normalized.province,
        "district": normalized.district,
        "previous_crop": normalized.previous_crop,
        "soil_type": normalized.soil_type,
        "sowing_date": normalized.sowing_date,
        "growth_stage": normalized.growth_stage,
        "problem": normalized.problem,
        "observations": normalized.observations,
        "farmer_question": normalized.farmer_question,
    }

    missing = [field for field in required if not values.get(field)]
    optionals = [field for field in optional if values.get(field)]
    return {"required": required, "optional": optional, "values": values, "missing": missing, "optionals": optionals}


def _evaluate_missing_information(normalized: NormalizedFarmerRequest, intent: AgriculturalIntent) -> dict[str, Any]:
    rules = _build_missing_information_rules(intent, normalized)
    missing = list(rules["missing"])
    required = rules["required"]
    optional = rules["optional"]
    risk = _determine_risk(intent, normalized)

    if intent == AgriculturalIntent.NUTRIENT_MANAGEMENT:
        if not normalized.soil_type:
            missing.append("soil_type")
    if intent == AgriculturalIntent.PEST_OR_DISEASE:
        if not normalized.observations:
            missing.append("observations")

    required_information = [field for field in required if field not in missing]
    missing_information = sorted(set(missing))
    optional_information = sorted(set(optional))

    safe_guidance = []
    if intent in {AgriculturalIntent.SOWING_PREPARATION, AgriculturalIntent.GENERAL_CROP_ADVICE}:
        safe_guidance = [
            "General seedbed preparation and residue management guidance can still be provided if the evidence is relevant.",
        ]
    elif intent == AgriculturalIntent.NUTRIENT_MANAGEMENT:
        safe_guidance = [
            "Fertilizer rates should be based on soil-test information and locally applicable recommendations.",
        ]
    elif intent == AgriculturalIntent.PEST_OR_DISEASE:
        safe_guidance = [
            "Use symptom-based observation questions before making any pest or disease recommendation.",
        ]

    answerable = not bool(missing_information)
    reason = "Information is sufficient for a general evidence-based answer." if answerable else "Critical context is missing before making a specific recommendation."

    if intent == AgriculturalIntent.NUTRIENT_MANAGEMENT and risk in {RiskLevel.MODERATE, RiskLevel.HIGH}:
        answerable = False
        reason = "Fertilizer planning requires relevant crop, soil, and evidence context before giving a recommendation."
    if intent == AgriculturalIntent.PEST_OR_DISEASE:
        answerable = False
        reason = "A diagnosis cannot be confirmed from the reported symptom alone. Additional information is required before disease or treatment recommendations can be made."
    if intent in {AgriculturalIntent.SOWING_PREPARATION, AgriculturalIntent.GENERAL_CROP_ADVICE} and normalized.crop:
        answerable = True
        reason = "General agronomic guidance can proceed with the available crop and context."

    return {
        "required_information": required_information,
        "missing_information": missing_information,
        "optional_information": optional_information,
        "follow_up_questions": _build_follow_up_questions(intent, normalized),
        "answerable": answerable,
        "reason": reason,
        "risk": risk,
        "safe_general_guidance": safe_guidance,
    }


def _build_follow_up_questions(intent: AgriculturalIntent, normalized: NormalizedFarmerRequest) -> list[str]:
    if intent == AgriculturalIntent.NUTRIENT_MANAGEMENT:
        return [
            "Do you have recent soil-test information for this field?",
            "What is your current crop, previous crop, and soil type?",
        ]
    if intent == AgriculturalIntent.PEST_OR_DISEASE:
        return [
            "What symptoms are visible on the leaves, stems, or roots?",
            "What is the crop growth stage?",
            "How quickly is the problem spreading?",
        ]
    if intent == AgriculturalIntent.VARIETY_SELECTION:
        return [
            "Do you want a recommendation for a specific district or production system?",
        ]
    return ["Can you share more details about your field and the problem you are facing?"]


def _build_evidence_bundle(evidence: list[Any]) -> EvidenceBundle:
    source_paths = []
    provenance = []
    versions = []
    conflicts = []
    quality_summary = {"insufficient": 0, "general": 0, "moderate": 0, "strong": 0}

    for item in evidence:
        source_paths.append(item.source)
        if getattr(item, "provenance", None) is not None:
            provenance.append(item.provenance)
        if getattr(item, "document_version", None):
            versions.append(item.document_version)
        quality_name = getattr(item.quality, "value", str(item.quality)).lower()
        if quality_name in quality_summary:
            quality_summary[quality_name] += 1

    if evidence:
        conflicts = detect_conflicts(evidence)

    bundle = EvidenceBundle(
        evidence_items=evidence,
        source_paths=source_paths,
        provenance=provenance,
        versions=versions,
        conflicts=conflicts,
        quality_summary=quality_summary,
        local_specificity="local" if any("punjab" in item.source.lower() for item in evidence) else "general",
        evidence_available=bool(evidence),
    )
    return bundle


def _build_local_fallback_response(question: str, normalized: NormalizedFarmerRequest, evidence: list[Any], decision_plan: Any, intent: AgriculturalIntent, risk: RiskLevel) -> AgriculturalResponse:
    evidence_sources = [item.source for item in evidence]
    recommendations = [
        "Use the retrieved agronomic guidance to form a general recommendation without making unsupported specific claims.",
        "Ask for soil-test results or field observations before acting on fertilizer, pesticide, or disease treatment decisions.",
    ]
    if intent == AgriculturalIntent.NUTRIENT_MANAGEMENT:
        recommendations = [
            "Use soil-test information and locally applicable agronomic guidance to determine nutrient requirements.",
            "Do not present a precise fertilizer rate without field-specific evidence.",
        ]
    elif intent == AgriculturalIntent.PEST_OR_DISEASE:
        recommendations = [
            "Collect symptom details, crop growth stage, and spread pattern before recommending any treatment.",
            "Avoid specific pesticide or disease treatment recommendations unless they are supported by label and local evidence.",
        ]
    elif intent == AgriculturalIntent.SOWING_PREPARATION:
        recommendations = [
            "Prepare a level seedbed with appropriate soil moisture and manage residue appropriately.",
            "Use local recommendations to confirm sowing timing and field conditions.",
        ]

    return AgriculturalResponse(
        situation=(normalized.problem or question or "Farmer query"),
        assessment="General evidence-grounded guidance based on the local knowledge base and current context.",
        recommendations=recommendations,
        reasons="The recommendation is grounded in locally retrieved agronomic evidence and restricted to low-risk, non-specific advice when exact field-specific claims are not available.",
        missing_information=[],
        warnings=["High-risk recommendations require field observations, soil-test information, and local expert verification."],
        confidence="Moderate",
        evidence_sources=evidence_sources,
        next_questions=["Can you share more details about soil conditions, symptoms, or field observations?"],
        intent=intent,
        risk_level=risk,
        safety_validated=True,
        validation_issues=[],
    )


def _maybe_call_llm_for_final_answer(question: str, context: Optional[FarmerContext], normalized: NormalizedFarmerRequest, evidence: list[Any], decision_plan: Any, intent: AgriculturalIntent, risk: RiskLevel):
    try:
        return ask_adviser(context, question) if context else ask_adviser(FarmerContext(crop=normalized.crop or "General crop", country=normalized.country or "Pakistan", problem=question), question)
    except Exception:
        return _build_local_fallback_response(question, normalized, evidence, decision_plan, intent, risk)


def ask_farmer(
    question: str,
    context: Optional[FarmerContext] = None,
    conversation_history: Optional[list[str]] = None,
    language: Optional[str] = None,
    urgency: Optional[str] = None,
) -> OrchestrationOutcome:
    query = FarmerQueryInput(
        raw_text=question,
        context=context,
        conversation_history=conversation_history,
        language=language,
        urgency=urgency,
    )
    normalized = normalize_farmer_query(query)

    crop = normalized.crop or (context.crop if context else None) or "crop"
    farmer_question = normalized.farmer_question or question
    intent = classify_agricultural_intent(farmer_question, context)
    risk = _determine_risk(intent, normalized)

    missing_info = _evaluate_missing_information(normalized, intent)
    if not missing_info["answerable"]:
        clarification = ClarificationResult(
            missing_information=missing_info["missing_information"],
            why_it_matters=missing_info["reason"],
            follow_up_questions=missing_info["follow_up_questions"],
            safe_general_guidance=missing_info["safe_general_guidance"],
            reason=missing_info["reason"],
        )
        return OrchestrationOutcome(is_clarification_required=True, clarification=clarification)

    case = AgriculturalCase(
        crop=normalized.crop,
        location=", ".join(part for part in [normalized.country, normalized.province, normalized.district] if part),
        province=normalized.province,
        district=normalized.district,
        previous_crop=normalized.previous_crop,
        soil_type=normalized.soil_type,
        irrigation=normalized.irrigation,
        sowing_date=normalized.sowing_date,
        growth_stage=normalized.growth_stage,
        problem=normalized.problem,
        farmer_question=farmer_question,
    )
    decision_plan = build_decision_plan(case, intent)
    retrieval_query = decision_plan.retrieval_query or farmer_question
    evidence = LocalKnowledgeRetriever().retrieve(retrieval_query, top_k=3)
    evidence_bundle = _build_evidence_bundle(evidence)

    if not evidence_bundle.evidence_available:
        clarification = ClarificationResult(
            missing_information=["No local evidence matched the farmer query."],
            why_it_matters="The system needs relevant local agronomic evidence before giving a final recommendation.",
            follow_up_questions=["Can you provide more detail about the crop, location, and problem?"],
            safe_general_guidance=["General agronomic guidance may still be offered, but it should be presented as tentative and non-specific."],
            reason="No relevant local evidence was found.",
        )
        return OrchestrationOutcome(is_clarification_required=True, clarification=clarification)

    response = _maybe_call_llm_for_final_answer(farmer_question, context, normalized, evidence, decision_plan, intent, risk)

    if isinstance(response, str):
        validated_text, is_safe, issues = validate_response_detailed(response)
        if not is_safe:
            clarification = ClarificationResult(
                missing_information=["The response contains unsupported or risky claims."],
                why_it_matters="The advice must be verified before a specific recommendation can be accepted.",
                follow_up_questions=["Please provide soil-test information, symptom details, or local label guidance before making a specific recommendation."],
                safe_general_guidance=["General agronomic guidance can be shared without exact product rates or treatment claims."],
                reason="Safety validation flagged unsupported specifics.",
            )
            return OrchestrationOutcome(is_clarification_required=True, clarification=clarification)

        return OrchestrationOutcome(
            is_clarification_required=False,
            response=AgriculturalResponse(
                situation=(normalized.problem or farmer_question or "Farmer query"),
                assessment="Evidence-grounded agricultural guidance based on the local knowledge base.",
                recommendations=["Review the advisory guidance and keep recommendations conservative."],
                reasons="This structured output is being returned as a compatibility wrapper around the existing decision and validation pipeline.",
                missing_information=missing_info["missing_information"],
                warnings=["Follow local agronomic guidance and verify high-risk recommendations."],
                confidence="Moderate",
                evidence_sources=evidence_bundle.source_paths,
                next_questions=missing_info["follow_up_questions"],
                intent=intent,
                risk_level=risk,
                safety_validated=is_safe,
                validation_issues=issues,
            ),
        )

    if isinstance(response, AgriculturalResponse):
        return OrchestrationOutcome(is_clarification_required=False, response=response)

    return OrchestrationOutcome(is_clarification_required=False, response=_build_local_fallback_response(farmer_question, normalized, evidence, decision_plan, intent, risk))
