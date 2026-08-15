from app.adviser import build_evidence_grounded_prompt, validate_response_text
from app.farmer_context import FarmerContext
from app.knowledge import EvidenceItem, EvidenceQuality, LocalKnowledgeRetriever, Recommendation, ClaimType, classify_claim_type, validate_recommendation


def test_evidence_quality_can_be_represented():
    item = EvidenceItem(
        source="knowledge/crops/wheat.md",
        title="Wheat",
        content="Rice-wheat systems require attention to residue management and seedbed preparation.",
        score=10,
        quality=EvidenceQuality.MODERATE,
    )

    assert item.quality == EvidenceQuality.MODERATE


def test_a_recommendation_can_reference_supporting_evidence():
    evidence = [
        EvidenceItem(
            source="knowledge/crops/wheat.md",
            title="Wheat",
            content="Residue management is important in rice-wheat systems.",
            score=8,
            quality=EvidenceQuality.MODERATE,
        )
    ]
    recommendation = Recommendation(
        text="Manage rice residue to support wheat establishment.",
        claim_type=ClaimType.RESIDUE,
        supporting_evidence=evidence,
        evidence_quality=EvidenceQuality.MODERATE,
        confidence="medium",
        needs_verification=False,
    )

    assert recommendation.supporting_evidence[0].source.endswith("wheat.md")


def test_general_wheat_recommendation_can_pass_validation():
    evidence = [
        EvidenceItem(
            source="knowledge/crops/wheat.md",
            title="Wheat",
            content="Wheat generally benefits from a well-prepared, level seedbed with suitable soil moisture and good seed-to-soil contact.",
            score=9,
            quality=EvidenceQuality.MODERATE,
        )
    ]
    recommendation = Recommendation(
        text="Prepare a well-levelled seedbed with suitable soil moisture before sowing wheat.",
        claim_type=ClaimType.SOWING,
        supporting_evidence=evidence,
        evidence_quality=EvidenceQuality.MODERATE,
        confidence="medium",
        needs_verification=False,
    )

    validated = validate_recommendation(recommendation)
    assert validated.needs_verification is False


def test_unsupported_fertilizer_rate_is_flagged():
    evidence = [
        EvidenceItem(
            source="knowledge/crops/wheat.md",
            title="Wheat",
            content="Nutrient requirements should ideally be determined using soil-test information and locally applicable agricultural recommendations.",
            score=7,
            quality=EvidenceQuality.MODERATE,
        )
    ]
    recommendation = Recommendation(
        text="Apply exactly 2 bags of DAP per acre.",
        claim_type=ClaimType.FERTILIZER,
        supporting_evidence=evidence,
        evidence_quality=EvidenceQuality.MODERATE,
        confidence="medium",
        needs_verification=False,
    )

    validated = validate_recommendation(recommendation)
    assert validated.needs_verification is True
    assert "verified local evidence" in (validated.warning or "").lower()


def test_unsupported_pesticide_recommendation_is_flagged():
    evidence = [
        EvidenceItem(
            source="knowledge/crops/wheat.md",
            title="Wheat",
            content="Pesticides should only be used according to the locally registered product label and applicable regulations.",
            score=8,
            quality=EvidenceQuality.MODERATE,
        )
    ]
    recommendation = Recommendation(
        text="Spray 500 ml/acre of pesticide X.",
        claim_type=ClaimType.PESTICIDE,
        supporting_evidence=evidence,
        evidence_quality=EvidenceQuality.MODERATE,
        confidence="medium",
        needs_verification=False,
    )

    validated = validate_recommendation(recommendation)
    assert validated.needs_verification is True
    assert "verified local label" in (validated.warning or "").lower()


def test_unsupported_specific_variety_recommendation_is_flagged():
    evidence = [
        EvidenceItem(
            source="knowledge/crops/wheat.md",
            title="Wheat",
            content="The appropriate sowing period depends on location, climate, variety, and local recommendations.",
            score=6,
            quality=EvidenceQuality.GENERAL,
        )
    ]
    recommendation = Recommendation(
        text="Plant Akbar-19 for Sahiwal.",
        claim_type=ClaimType.VARIETY,
        supporting_evidence=evidence,
        evidence_quality=EvidenceQuality.GENERAL,
        confidence="medium",
        needs_verification=False,
    )

    validated = validate_recommendation(recommendation)
    assert validated.needs_verification is True


def test_overly_confident_disease_diagnosis_is_flagged_or_handled_safely():
    recommendation = Recommendation(
        text="This wheat crop definitely has yellow rust.",
        claim_type=ClaimType.DISEASE,
        supporting_evidence=[],
        evidence_quality=EvidenceQuality.INSUFFICIENT,
        confidence="high",
        needs_verification=True,
    )

    validated = validate_recommendation(recommendation)
    assert validated.needs_verification is True
    assert validated.warning is not None


def test_no_evidence_queries_are_handled_safely():
    evidence = []
    recommendation = Recommendation(
        text="Use a specific pesticide schedule for wheat.",
        claim_type=ClaimType.PESTICIDE,
        supporting_evidence=evidence,
        evidence_quality=EvidenceQuality.INSUFFICIENT,
        confidence="low",
        needs_verification=True,
    )

    validated = validate_recommendation(recommendation)
    assert validated.needs_verification is True
    assert "not supported by retrieved evidence" in (validated.warning or "").lower()


def test_source_attribution_is_preserved():
    retriever = LocalKnowledgeRetriever()
    evidence = retriever.retrieve("Wheat after rice in Sahiwal")
    assert evidence
    assert any(item.source.endswith("wheat.md") for item in evidence)


def test_adviser_still_works_with_the_existing_wheat_rice_farmer_example():
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
    prompt = build_evidence_grounded_prompt(context, [
        {
            "source": "knowledge/crops/wheat.md",
            "title": "Wheat",
            "content": "Rice-wheat systems require attention to residue management and nutrient management.",
            "score": 9,
            "quality": "moderate",
        }
    ])

    assert "FARMER FACTS" in prompt
    assert "RETRIEVED EVIDENCE" in prompt
    assert "knowledge/crops/wheat.md" in prompt


def test_original_llm_smoke_test_still_works():
    response = validate_response_text("Wheat is typically sown during the Rabi season.")
    assert response == "Wheat is typically sown during the Rabi season."


def test_claim_type_classification():
    assert classify_claim_type("Which fertilizer should I apply?") == "fertilizer"
    assert classify_claim_type("What pesticide should I spray?") == "pesticide"
    assert classify_claim_type("Which wheat variety is best?") == "variety"
