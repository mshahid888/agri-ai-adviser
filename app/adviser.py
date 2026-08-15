from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from openai import OpenAI

from app.config import AGRI_AI_MODEL, OMNIROUTE_BASE_URL, require_omniroute_api_key
from app.farmer_context import FarmerContext
from app.knowledge import EvidenceItem, EvidenceQuality, LocalKnowledgeRetriever

SYSTEM_PROMPT = """
You are an evidence-grounded agricultural adviser.

Use farmer-provided information as FACTS.
Use retrieved agricultural knowledge as EVIDENCE.
Use your reasoning only as MODEL REASONING.
Keep these categories separate.

Rules:
- Farmer information is a fact only when stated by the farmer.
- Retrieved knowledge is evidence only when it appears in the retrieved text.
- Do not claim that information came from a source unless that source was actually retrieved.
- Do not invent weather, soil-test results, field measurements, government recommendations, product names, pesticide labels, fertilizer rates, crop varieties, or disease diagnoses.
- For chemical inputs, tell the farmer to follow the locally registered product label and applicable regulations.
- If evidence is insufficient, say that evidence is insufficient.
- If important information is missing, ask the farmer for it.
- Distinguish general agricultural guidance from location-specific advice.
- The answer should clearly separate: Farmer situation, Evidence available, Assessment, Practical recommendations, Missing information, Safety/uncertainty notes.
- Do not provide exact fertilizer or pesticide rates unless retrieved evidence specifically supports them.
- If a recommendation is high-risk or highly specific, it should carry a caution and require local confirmation.
Your goal is safe, evidence-grounded advice, not confident guessing.
"""


class AgriculturalIntent(str, Enum):
    SOWING_PREPARATION = "sowing_preparation"
    NUTRIENT_MANAGEMENT = "nutrient_management"
    IRRIGATION = "irrigation"
    PEST_OR_DISEASE = "pest_or_disease"
    WEED_MANAGEMENT = "weed_management"
    SOIL_MANAGEMENT = "soil_management"
    RESIDUE_MANAGEMENT = "residue_management"
    VARIETY_SELECTION = "variety_selection"
    GENERAL_CROP_ADVICE = "general_crop_advice"
    UNKNOWN = "unknown"


class RiskLevel(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


@dataclass
class AgriculturalCase:
    crop: str | None = None
    location: str | None = None
    province: str | None = None
    district: str | None = None
    previous_crop: str | None = None
    soil_type: str | None = None
    irrigation: str | None = None
    sowing_date: str | None = None
    growth_stage: str | None = None
    problem: str | None = None
    farmer_question: str | None = None
    soil_test_info: str | None = None

    @classmethod
    def from_farmer_context(cls, context: FarmerContext, farmer_question: str | None = None) -> "AgriculturalCase":
        location_parts = [part for part in [context.country, context.province, context.district] if part]
        return cls(
            crop=context.crop,
            location=", ".join(location_parts) if location_parts else None,
            province=context.province,
            district=context.district,
            previous_crop=context.previous_crop,
            soil_type=context.soil_type,
            irrigation=context.irrigation,
            sowing_date=context.sowing_date,
            growth_stage=context.growth_stage,
            problem=context.problem,
            farmer_question=farmer_question or context.problem,
        )


@dataclass
class AgriculturalDecisionPlan:
    intent: AgriculturalIntent
    known_facts: dict[str, str] = field(default_factory=dict)
    missing_information: list[str] = field(default_factory=list)
    retrieval_query: str = ""
    required_evidence_types: list[str] = field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    recommended_actions: list[str] = field(default_factory=list)
    questions_for_farmer: list[str] = field(default_factory=list)


def classify_agricultural_intent(question: str | None, context: FarmerContext | None = None) -> AgriculturalIntent:
    text = (question or "").lower()
    if not text and context:
        text = " ".join(filter(None, [context.crop, context.problem, context.previous_crop])).lower()

    if not text:
        return AgriculturalIntent.UNKNOWN

    if any(word in text for word in ["sow", "sowing", "planting", "seedbed", "when to sow", "plant date", "sowing date"]):
        return AgriculturalIntent.SOWING_PREPARATION
    if any(word in text for word in ["fertilizer", "dap", "urea", "nutrient", "nitrogen", "phosphorus", "potassium", "feed", "soil test"]):
        return AgriculturalIntent.NUTRIENT_MANAGEMENT
    if any(word in text for word in ["irrigation", "water", "moisture", "when to irrigate"]):
        return AgriculturalIntent.IRRIGATION
    if any(word in text for word in ["pesticide", "spray", "herbicide", "fungicide", "yellow leaves", "disease", "wilt", "rust", "leaf spot", "powdery mildew"]):
        return AgriculturalIntent.PEST_OR_DISEASE
    if any(word in text for word in ["weed", "weeds", "herbicide", "weed control"]):
        return AgriculturalIntent.WEED_MANAGEMENT
    if any(word in text for word in ["soil", "texture", "salinity", "structure", "loam", "soil management"]):
        return AgriculturalIntent.SOIL_MANAGEMENT
    if any(word in text for word in ["residue", "straw", "rice straw", "burning residue", "residue management"]):
        return AgriculturalIntent.RESIDUE_MANAGEMENT
    if any(word in text for word in ["variety", "cultivar", "seed variety", "which variety"]):
        return AgriculturalIntent.VARIETY_SELECTION
    if any(word in text for word in ["advice", "help", "what should i do", "management", "recommendation"]):
        return AgriculturalIntent.GENERAL_CROP_ADVICE
    return AgriculturalIntent.UNKNOWN


def build_information_requirements(intent: AgriculturalIntent) -> dict[str, list[str]]:
    return {
        AgriculturalIntent.SOWING_PREPARATION: {
            "required": ["crop", "country", "province", "district", "sowing_date", "previous_crop", "soil_type", "irrigation"],
            "optional": ["growth_stage", "problem"],
        },
        AgriculturalIntent.NUTRIENT_MANAGEMENT: {
            "required": ["crop", "country", "soil_type", "previous_crop"],
            "optional": ["province", "district", "yield_target", "soil_test_info"],
        },
        AgriculturalIntent.IRRIGATION: {
            "required": ["crop", "country", "soil_type", "irrigation"],
            "optional": ["province", "district", "sowing_date", "problem"],
        },
        AgriculturalIntent.PEST_OR_DISEASE: {
            "required": ["crop", "growth_stage", "problem"],
            "optional": ["province", "district", "soil_type", "irrigation", "severity", "symptoms"],
        },
        AgriculturalIntent.WEED_MANAGEMENT: {
            "required": ["crop", "problem"],
            "optional": ["growth_stage", "province", "district"],
        },
        AgriculturalIntent.SOIL_MANAGEMENT: {
            "required": ["crop", "soil_type"],
            "optional": ["province", "district", "previous_crop", "irrigation"],
        },
        AgriculturalIntent.RESIDUE_MANAGEMENT: {
            "required": ["crop", "previous_crop", "problem"],
            "optional": ["province", "district", "soil_type"],
        },
        AgriculturalIntent.VARIETY_SELECTION: {
            "required": ["crop", "country", "province", "district"],
            "optional": ["previous_crop", "soil_type", "sowing_date"],
        },
        AgriculturalIntent.GENERAL_CROP_ADVICE: {
            "required": ["crop", "country"],
            "optional": ["province", "district", "problem", "soil_type"],
        },
        AgriculturalIntent.UNKNOWN: {
            "required": ["crop"],
            "optional": ["country", "province", "district", "problem"],
        },
    }.get(intent, {"required": [], "optional": []})


def determine_missing_information(case: AgriculturalCase, intent: AgriculturalIntent) -> tuple[dict[str, str], list[str], list[str]]:
    requirements = build_information_requirements(intent)
    known: dict[str, str] = {}
    missing: list[str] = []
    optional: list[str] = []

    for field in requirements["required"]:
        value = getattr(case, field, None)
        if value:
            known[field] = str(value)
        else:
            missing.append(field)

    for field in requirements["optional"]:
        value = getattr(case, field, None)
        if value:
            known[field] = str(value)
        else:
            optional.append(field)

    return known, missing, optional


def build_retrieval_query(case: AgriculturalCase, intent: AgriculturalIntent) -> str:
    parts: list[str] = []

    if case.crop:
        parts.append(case.crop)
    if case.province or case.district:
        location_text = ", ".join(part for part in [case.province, case.district] if part)
        if location_text:
            parts.append(location_text)
    if case.previous_crop and case.crop:
        parts.append(f"{case.crop} after {case.previous_crop}")
    if case.soil_type:
        parts.append(case.soil_type)
    if case.irrigation:
        parts.append(case.irrigation)
    if case.sowing_date:
        parts.append(case.sowing_date)
    if case.problem:
        parts.append(case.problem)

    intent_keywords = {
        AgriculturalIntent.SOWING_PREPARATION: ["sowing", "seedbed", "soil moisture", "residue management"],
        AgriculturalIntent.NUTRIENT_MANAGEMENT: ["nutrient management", "soil fertility", "soil test", "previous crop"],
        AgriculturalIntent.IRRIGATION: ["irrigation", "water requirement", "soil moisture"],
        AgriculturalIntent.PEST_OR_DISEASE: ["pest", "disease", "symptoms", "crop stage"],
        AgriculturalIntent.WEED_MANAGEMENT: ["weed management", "weed control"],
        AgriculturalIntent.SOIL_MANAGEMENT: ["soil structure", "soil management", "texture"],
        AgriculturalIntent.RESIDUE_MANAGEMENT: ["rice residue", "residue management", "straw management"],
        AgriculturalIntent.VARIETY_SELECTION: ["variety recommendation", "local recommendation", "seed selection"],
        AgriculturalIntent.GENERAL_CROP_ADVICE: ["crop management", "general guidance"],
        AgriculturalIntent.UNKNOWN: ["crop management"],
    }

    parts.extend(intent_keywords.get(intent, ["crop management"]))
    return " ".join(parts)


def determine_risk_level(intent: AgriculturalIntent) -> RiskLevel:
    if intent in {AgriculturalIntent.SOWING_PREPARATION, AgriculturalIntent.GENERAL_CROP_ADVICE, AgriculturalIntent.RESIDUE_MANAGEMENT}:
        return RiskLevel.LOW
    if intent in {AgriculturalIntent.NUTRIENT_MANAGEMENT, AgriculturalIntent.IRRIGATION, AgriculturalIntent.SOIL_MANAGEMENT, AgriculturalIntent.WEED_MANAGEMENT}:
        return RiskLevel.MODERATE
    if intent in {AgriculturalIntent.PEST_OR_DISEASE, AgriculturalIntent.VARIETY_SELECTION}:
        return RiskLevel.HIGH
    return RiskLevel.MODERATE


def apply_expert_rules(case: AgriculturalCase, intent: AgriculturalIntent) -> tuple[list[str], list[str]]:
    actions: list[str] = []
    questions: list[str] = []

    if case.crop and case.previous_crop and case.crop.lower() == "wheat" and case.previous_crop.lower() == "rice":
        actions.extend([
            "Give extra attention to rice residue management and seedbed quality.",
            "Check soil structure and moisture before sowing.",
            "Review nutrient management requirements for the rice-wheat system.",
        ])

    if intent == AgriculturalIntent.NUTRIENT_MANAGEMENT:
        questions.append("Do you have soil-test information or local nutrient recommendation evidence?")
        actions.append("Do not give exact fertilizer rates without supporting soil-test or local recommendation evidence.")

    if intent == AgriculturalIntent.PEST_OR_DISEASE:
        questions.extend([
            "What are the visible symptoms and which plant parts are affected?",
            "What is the crop growth stage?",
            "How severe is the issue and how quickly is it spreading?",
        ])
        actions.append("Treat disease diagnosis as tentative unless field observations and local evidence support it.")

    if intent == AgriculturalIntent.VARIETY_SELECTION:
        questions.append("What locally verified variety information is available for this location?")
        actions.append("Do not recommend a specific variety without verified local evidence.")

    if intent == AgriculturalIntent.RESIDUE_MANAGEMENT and case.previous_crop and case.previous_crop.lower() == "rice":
        actions.append("Avoid open burning when possible and consider residue management options suited to local conditions.")

    return actions, questions


def build_decision_plan(case: AgriculturalCase, intent: AgriculturalIntent | None = None) -> AgriculturalDecisionPlan:
    intent = intent or classify_agricultural_intent(case.farmer_question or case.problem, None)
    known_facts, missing_info, optional_info = determine_missing_information(case, intent)
    actions, questions = apply_expert_rules(case, intent)
    risk = determine_risk_level(intent)
    retrieval_query = build_retrieval_query(case, intent)
    required_evidence_map = {
        AgriculturalIntent.SOWING_PREPARATION: ["sowing", "seedbed", "soil moisture", "residue management", "rice-wheat rotation"],
        AgriculturalIntent.NUTRIENT_MANAGEMENT: ["soil fertility", "nutrient management", "soil-test", "previous crop"],
        AgriculturalIntent.IRRIGATION: ["irrigation", "soil moisture", "water requirement"],
        AgriculturalIntent.PEST_OR_DISEASE: ["crop symptoms", "disease or pest information", "crop stage"],
        AgriculturalIntent.WEED_MANAGEMENT: ["weed management"],
        AgriculturalIntent.SOIL_MANAGEMENT: ["soil structure", "soil management"],
        AgriculturalIntent.RESIDUE_MANAGEMENT: ["residue management", "rice straw"],
        AgriculturalIntent.VARIETY_SELECTION: ["variety recommendation", "local evidence"],
        AgriculturalIntent.GENERAL_CROP_ADVICE: ["general crop guidance"],
        AgriculturalIntent.UNKNOWN: ["general crop guidance"],
    }

    if intent == AgriculturalIntent.PEST_OR_DISEASE and case.problem and any(keyword in case.problem.lower() for keyword in ["spray", "pesticide", "dose", "per acre"]):
        risk = RiskLevel.HIGH
        questions.append("What are the symptoms, which plant parts are affected, and what is the growth stage?")
        actions.append("Do not invent a pesticide or application rate without verified local evidence and label guidance.")

    plan = AgriculturalDecisionPlan(
        intent=intent,
        known_facts=known_facts,
        missing_information=missing_info,
        retrieval_query=retrieval_query,
        required_evidence_types=required_evidence_map.get(intent, ["general crop guidance"]),
        risk_level=risk,
        recommended_actions=actions,
        questions_for_farmer=questions,
    )
    if optional_info:
        plan.questions_for_farmer.extend([f"Optional information that may help: {item}." for item in optional_info])
    return plan


def build_decision_prompt(context: FarmerContext, evidence: list[EvidenceItem | dict], decision_plan: AgriculturalDecisionPlan | None = None) -> str:
    facts = context.to_prompt()
    evidence_text = format_evidence(evidence)
    plan = decision_plan or build_decision_plan(AgriculturalCase.from_farmer_context(context, context.problem))
    return f"""AGRICULTURAL EXPERT DECISION LAYER

FARMER FACTS:
{facts}

INTENT:
{plan.intent.value}

RISK LEVEL:
{plan.risk_level.value}

KNOWN INFORMATION:
{plan.known_facts}

MISSING INFORMATION:
{plan.missing_information or 'None noted'}

RETRIEVAL QUERY:
{plan.retrieval_query}

REQUIRED EVIDENCE TYPES:
{plan.required_evidence_types}

RETRIEVED EVIDENCE:
{evidence_text}

DECISION RULES:
- Use the decision plan as a reasoning framework, not as scientific evidence.
- Do not invent local recommendations, soil-test results, pesticide rates, or disease diagnoses.
- If evidence is insufficient, say so clearly.
- Ask only targeted questions when critical information is missing.
- Give practical general guidance when the evidence supports it.

Response structure required:
1. Assessment
2. Evidence
3. Recommended actions
4. Important limitations
5. Information needed
6. Safety and verification notes
"""


def build_query(context: FarmerContext) -> str:
    return " ".join(
        part for part in [
            context.crop,
            context.country,
            context.province,
            context.district,
            context.previous_crop,
            context.soil_type,
            context.irrigation,
            context.sowing_date,
            context.problem,
        ] if part
    )


def format_evidence(evidence: list[EvidenceItem | dict]) -> str:
    if not evidence:
        return "No relevant evidence available."

    sections = []
    for item in evidence:
        if isinstance(item, dict):
            source = item.get("source", "unknown")
            title = item.get("title", "Evidence")
            content = item.get("content", "")
            score = item.get("score", 0)
            quality = item.get("quality", EvidenceQuality.GENERAL.value)
        else:
            source = item.source
            title = item.title
            content = item.content
            score = item.score
            quality = item.quality.value

        sections.append(
            f"SOURCE: {source}\n"
            f"TITLE: {title}\n"
            f"QUALITY: {quality}\n"
            f"RELEVANCE SCORE: {score}\n"
            f"{content.strip()}"
        )
    return "\n\n".join(sections)


def build_evidence_grounded_prompt(context: FarmerContext, evidence: list[EvidenceItem | dict]) -> str:
    facts = context.to_prompt()
    evidence_text = format_evidence(evidence)
    return f"""EVIDENCE-GROUNDED AGRICULTURAL ADVISER

FARMER FACTS:
{facts}

RETRIEVED EVIDENCE:
{evidence_text}

Response structure required:
1. Farmer situation
2. Evidence available
3. Assessment
4. Practical recommendations
5. What cannot be determined
6. Information needed
7. Safety and uncertainty notes

Important rules:
- Do not blend facts, evidence, and recommendations together.
- Use only the retrieved evidence as supportable agricultural knowledge.
- Do not invent exact fertilizer rates, pesticide doses, varieties, or disease diagnoses.
- If evidence is insufficient, state that clearly.
- Show sources as retrieved file paths when relevant.
"""


def validate_response_text(response_text: str) -> str:
    cleaned = response_text.strip()
    if not cleaned:
        return "No response received from the model."

    lower = cleaned.lower()
    high_risk_patterns = [
        r"\b\d+\s*(bags?|kg|kg/acre|ml|litres?|liters?)\b",
        r"\bapply .*\bper acre\b",
        r"\bthis is .*disease\b",
        r"\bvariety .* is recommended\b",
        r"\buse .*pesticide\b",
        "exactly which pesticide",
        "exact fertilizer",
    ]
    matches = [pattern for pattern in high_risk_patterns if re.search(pattern, lower)]

    if matches:
        return (
            "Safety warning: the model output contains a potentially unsupported high-risk recommendation. "
            "The system should treat this as needing local verification and should not present it as confirmed advice."
        )

    return cleaned


def ask_adviser(context: FarmerContext, farmer_question: str | None = None) -> str:
    question = farmer_question or context.problem or context.crop or ""
    case = AgriculturalCase.from_farmer_context(context, question)
    intent = classify_agricultural_intent(question, context)
    decision_plan = build_decision_plan(case, intent)
    retrieval_query = decision_plan.retrieval_query or build_query(context)
    retriever = LocalKnowledgeRetriever()
    evidence = retriever.retrieve(retrieval_query, top_k=3)
    user_message = build_decision_prompt(context, evidence, decision_plan)

    api_key = require_omniroute_api_key()
    client = OpenAI(
        base_url=OMNIROUTE_BASE_URL,
        api_key=api_key,
    )

    response = client.chat.completions.create(
        model=AGRI_AI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )
    answer = response.choices[0].message.content
    validated = validate_response_text(answer)
    if validated.startswith("Safety warning:"):
        return validated
    return answer


if __name__ == "__main__":
    farmer = FarmerContext(
        crop="Wheat",
        country="Pakistan",
        province="Punjab",
        district="Sahiwal",
        previous_crop="Rice",
        soil_type="Loam",
        irrigation="Canal + tube well",
        sowing_date="10 November",
        problem="Preparing for sowing",
    )
    print("===== EVIDENCE-GROUNDED AGRICULTURAL ADVISER =====")
    print(ask_adviser(farmer))
