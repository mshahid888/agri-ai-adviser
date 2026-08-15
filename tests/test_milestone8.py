from app.farmer_context import FarmerContext
from app.orchestration import (
    ClarificationResult,
    FarmerQueryInput,
    NormalizedFarmerRequest,
    ask_farmer,
    normalize_farmer_query,
)


def test_basic_farmer_query_normalization():
    request = FarmerQueryInput(
        raw_text="I am growing wheat in Sahiwal, Punjab, Pakistan. Last crop was rice.",
        language="en",
        urgency="normal",
    )

    normalized = normalize_farmer_query(request)

    assert normalized.crop.lower() == "wheat"
    assert normalized.country.lower() == "pakistan"
    assert normalized.province.lower() == "punjab"
    assert normalized.district.lower() == "sahiwal"
    assert normalized.previous_crop.lower() == "rice"


def test_explicit_facts_are_preserved():
    context = FarmerContext(
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

    request = FarmerQueryInput(
        raw_text="I am preparing for wheat sowing in Sahiwal.",
        context=context,
    )

    normalized = normalize_farmer_query(request)

    assert normalized.crop.lower() == "wheat"
    assert normalized.soil_type.lower() == "loam"
    assert normalized.previous_crop.lower() == "rice"
    assert normalized.farmer_question.lower().startswith("preparing")


def test_missing_facts_are_not_invented():
    request = FarmerQueryInput(raw_text="I need advice about wheat")
    normalized = normalize_farmer_query(request)

    assert normalized.crop.lower() == "wheat"
    assert normalized.country is None
    assert normalized.province is None
    assert normalized.district is None


def test_general_low_risk_question_can_proceed():
    outcome = ask_farmer("How should I prepare a wheat seedbed in Punjab?")

    assert outcome.is_clarification_required is False
    assert outcome.response is not None
    assert outcome.response.intent.value in {"sowing_preparation", "general_crop_advice"}


def test_fertilizer_question_triggers_missing_info_check():
    outcome = ask_farmer("How much urea should I apply for wheat?")

    assert outcome.is_clarification_required is True
    assert outcome.clarification is not None
    assert outcome.clarification.missing_information


def test_pesticide_high_risk_request_triggers_stricter_checks():
    outcome = ask_farmer("What pesticide should I spray for yellow rust on wheat?")

    assert outcome.is_clarification_required is True
    assert outcome.clarification is not None
    assert any("symptom" in q.lower() or "growth stage" in q.lower() for q in outcome.clarification.follow_up_questions)


def test_disease_symptom_request_does_not_invent_diagnosis():
    outcome = ask_farmer("My wheat leaves are yellow. What should I do?")

    assert outcome.is_clarification_required is True
    assert outcome.clarification is not None
    assert "diagnosis" in outcome.clarification.why_it_matters.lower() or "symptoms" in outcome.clarification.why_it_matters.lower()


def test_retrieval_is_still_content_first():
    from app.knowledge import LocalKnowledgeRetriever

    retriever = LocalKnowledgeRetriever()
    results = retriever.retrieve("Wheat after rice in Sahiwal")

    assert results
    assert results[0].source.endswith("wheat.md")


def test_provenance_is_preserved_in_orchestration_bundle():
    from app.knowledge import LocalKnowledgeRetriever, detect_conflicts

    retriever = LocalKnowledgeRetriever()
    evidence = retriever.retrieve("Wheat in Punjab")
    conflicts = detect_conflicts(evidence)

    assert evidence
    assert evidence[0].provenance is not None or evidence[0].document_version is not None
    assert conflicts is not None


def test_clarification_response_is_structured():
    outcome = ask_farmer("How much urea should I apply for wheat?")

    assert isinstance(outcome.clarification, ClarificationResult)
    assert outcome.clarification.missing_information
    assert outcome.clarification.follow_up_questions
    assert outcome.clarification.reason


def test_final_response_remains_compatible():
    outcome = ask_farmer("How should I prepare a wheat seedbed in Punjab?")

    assert outcome.response is not None
    assert outcome.response.situation
    assert outcome.response.recommendations
    assert outcome.response.confidence


def test_orchestration_does_not_call_llm_when_clarification_is_sufficient(monkeypatch):
    def _fail_if_called(*args, **kwargs):
        raise AssertionError("LLM should not be called when clarification is sufficient")

    import app.orchestration as orchestration

    monkeypatch.setattr(orchestration, "_maybe_call_llm_for_final_answer", _fail_if_called)

    outcome = ask_farmer("How much urea should I apply for wheat?")
    assert outcome.is_clarification_required is True
    assert outcome.clarification is not None
