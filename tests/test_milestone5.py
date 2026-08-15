from app.adviser import (
    AgriculturalCase,
    AgriculturalIntent,
    build_decision_plan,
    build_decision_prompt,
    classify_agricultural_intent,
)
from app.farmer_context import FarmerContext


def test_farmer_context_can_be_converted_to_agricultural_case():
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

    case = AgriculturalCase.from_farmer_context(farmer, farmer.problem)

    assert case.crop == "Wheat"
    assert case.previous_crop == "Rice"
    assert case.location == "Pakistan, Punjab, Sahiwal"
    assert case.farmer_question == "Preparing for sowing"


def test_agricultural_intent_classification_works_for_common_farmer_questions():
    farmer = FarmerContext(crop="Wheat", country="Pakistan", problem="Need sowing advice")
    assert classify_agricultural_intent("When should I sow wheat?", farmer) == AgriculturalIntent.SOWING_PREPARATION
    assert classify_agricultural_intent("What fertilizer should I apply?", farmer) == AgriculturalIntent.NUTRIENT_MANAGEMENT
    assert classify_agricultural_intent("My wheat has yellow rust symptoms", farmer) == AgriculturalIntent.PEST_OR_DISEASE


def test_decision_plan_builds_a_reasonable_query_and_risk_level():
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
    case = AgriculturalCase.from_farmer_context(farmer, farmer.problem)
    plan = build_decision_plan(case, AgriculturalIntent.SOWING_PREPARATION)

    assert plan.intent == AgriculturalIntent.SOWING_PREPARATION
    assert "Wheat" in plan.retrieval_query
    assert "Rice" in plan.retrieval_query or "sowing" in plan.retrieval_query.lower()
    assert plan.risk_level.value in {"low", "moderate", "high"}


def test_decision_prompt_includes_evidence_and_decision_metadata():
    farmer = FarmerContext(
        crop="Wheat",
        country="Pakistan",
        province="Punjab",
        district="Sahiwal",
        previous_crop="Rice",
        problem="Preparing for sowing",
    )
    case = AgriculturalCase.from_farmer_context(farmer, farmer.problem)
    plan = build_decision_plan(case, AgriculturalIntent.SOWING_PREPARATION)
    prompt = build_decision_prompt(
        farmer,
        [
            {
                "source": "knowledge/crops/wheat.md",
                "title": "Wheat",
                "content": "Rice-wheat systems require attention to residue management and seedbed preparation.",
                "score": 9,
                "quality": "moderate",
            }
        ],
        plan,
    )

    assert "AGRICULTURAL EXPERT DECISION LAYER" in prompt
    assert "INTENT" in prompt
    assert "RETRIEVED EVIDENCE" in prompt
    assert "knowledge/crops/wheat.md" in prompt
