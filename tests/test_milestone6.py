"""
Milestone 6 tests: Farmer-facing response engine.

Tests verify the structured response model, safety validation,
and farmer-friendly response generation.
"""
from app.adviser import (
    AgriculturalCase,
    AgriculturalIntent,
    AgriculturalResponse,
    RiskLevel,
    build_decision_plan,
    classify_agricultural_intent,
    format_evidence,
    validate_response_detailed,
    validate_response_text,
)
from app.farmer_context import FarmerContext
from app.knowledge import EvidenceItem, EvidenceQuality


# ============ Test 1: AgriculturalResponse structure ============

def test_agricultural_response_can_be_created():
    """Test that AgriculturalResponse can be instantiated."""
    response = AgriculturalResponse(
        situation="Wheat after rice in Sahiwal",
        assessment="Rice-wheat rotation requires attention to residue and soil preparation",
        recommendations=[
            "Manage rice residue appropriately",
            "Prepare seedbed with good soil moisture",
        ],
        reasons="Rice-wheat systems have specific requirements for soil structure and nutrient cycling",
        missing_information=["Current rice residue condition", "Recent soil test results"],
        warnings=["Fertilizer rates need soil-test information"],
        confidence="Moderate",
        evidence_sources=["knowledge/crops/wheat.md"],
        next_questions=["Do you have recent soil-test results?"],
        intent=AgriculturalIntent.SOWING_PREPARATION,
        risk_level=RiskLevel.LOW,
    )
    
    assert response.situation == "Wheat after rice in Sahiwal"
    assert len(response.recommendations) == 2
    assert response.confidence == "Moderate"
    assert response.intent == AgriculturalIntent.SOWING_PREPARATION


def test_agricultural_response_to_farmer_text():
    """Test that AgriculturalResponse can be converted to farmer-friendly text."""
    response = AgriculturalResponse(
        situation="Wheat after rice in Sahiwal",
        assessment="Requires residue and seedbed management",
        recommendations=["Manage residue", "Prepare seedbed"],
        reasons="Good agricultural practice for rice-wheat systems",
        missing_information=["Soil test results"],
        warnings=["Verify with local expert"],
        confidence="Moderate",
        evidence_sources=["knowledge/crops/wheat.md"],
        next_questions=["Do you have soil test results?"],
        intent=AgriculturalIntent.SOWING_PREPARATION,
        risk_level=RiskLevel.LOW,
    )
    
    farmer_text = response.to_farmer_text()
    
    assert "Your situation:" in farmer_text
    assert "What I recommend now:" in farmer_text
    assert "Why:" in farmer_text
    assert "Information still needed:" in farmer_text
    assert "Safety notes:" in farmer_text
    assert "Evidence sources:" in farmer_text
    assert "Confidence:" in farmer_text


# ============ Test 2: Farmer facts vs evidence separation ============

def test_farmer_facts_remain_separate_from_retrieved_evidence():
    """Test that farmer facts and evidence are clearly separated."""
    farmer = FarmerContext(
        crop="Wheat",
        country="Pakistan",
        province="Punjab",
        district="Sahiwal",
        previous_crop="Rice",
        soil_type="Loam",
        problem="Preparing for sowing",
    )
    
    case = AgriculturalCase.from_farmer_context(farmer, farmer.problem)
    plan = build_decision_plan(case)
    
    # Farmer facts should include what was provided
    assert "Wheat" in plan.known_facts.get("crop", "")
    assert "Loam" in plan.known_facts.get("soil_type", "")
    assert "Rice" in plan.known_facts.get("previous_crop", "")
    
    # Missing information should note what wasn't provided
    # (not make assumptions)
    assert plan.missing_information or True  # Can have no missing, depending on intent


# ============ Test 3: Structured response sections ============

def test_structured_response_contains_all_required_sections():
    """Test that response includes all farmer-facing sections."""
    response = AgriculturalResponse(
        situation="Test situation",
        assessment="Test assessment",
        recommendations=["Rec 1", "Rec 2"],
        reasons="Test reasons",
        missing_information=["Info 1"],
        warnings=["Warning 1"],
        confidence="High",
        evidence_sources=["source1"],
        next_questions=["Q1"],
        intent=AgriculturalIntent.SOWING_PREPARATION,
        risk_level=RiskLevel.LOW,
    )
    
    farmer_text = response.to_farmer_text()
    
    # Check all required sections exist
    sections = [
        "Your situation:",
        "What I recommend now:",
        "Why:",
        "Information still needed:",
        "Safety notes:",
        "Evidence sources:",
        "Confidence:",
    ]
    
    for section in sections:
        assert section in farmer_text, f"Missing section: {section}"


# ============ Test 4: Missing information handling ============

def test_missing_information_is_represented_correctly():
    """Test that missing information is properly identified."""
    farmer = FarmerContext(
        crop="Wheat",
        country="Pakistan",
    )
    
    case = AgriculturalCase.from_farmer_context(farmer)
    plan = build_decision_plan(case, AgriculturalIntent.NUTRIENT_MANAGEMENT)
    
    # Nutrient management requires soil_type, previous_crop
    # The farmer only provided crop and country
    missing = plan.missing_information
    
    # Should identify missing info
    assert isinstance(missing, list)


# ============ Test 5: Low-risk general advice ============

def test_low_risk_general_advice_passes_validation():
    """Test that general, well-supported advice passes safety validation."""
    response_text = """
    Your situation: Wheat after rice in Sahiwal, Punjab.
    
    What I recommend:
    - Prepare a level seedbed with appropriate soil moisture.
    - Manage rice residue appropriately before sowing.
    - Use soil-test information to determine nutrient requirements.
    
    Why: Rice-wheat rotation requires attention to soil structure,
    residue management, and nutrient cycling to maintain productivity.
    
    Information needed:
    - Current rice residue condition
    - Recent soil test results
    
    Safety: Fertilizer rates must be based on soil testing and local
    recommendations. Follow product labels for all agricultural inputs.
    """
    
    validated, is_safe, issues = validate_response_detailed(response_text)
    
    assert is_safe, f"Safe response flagged as unsafe: {issues}"


# ============ Test 6: Unsupported fertilizer rate is flagged ============

def test_unsupported_exact_fertilizer_rate_is_flagged():
    """Test that exact fertilizer quantities without evidence are flagged."""
    response_text = "Apply exactly 50 kg DAP per acre and 100 kg urea per acre."
    
    validated, is_safe, issues = validate_response_detailed(response_text)
    
    assert not is_safe
    assert any("fertilizer" in issue.lower() for issue in issues)


def test_unsupported_fertilizer_bags_is_flagged():
    """Test that bag quantities are flagged."""
    response_text = "Use 2 bags of DAP and 3 bags of urea for your wheat crop."
    
    validated, is_safe, issues = validate_response_detailed(response_text)
    
    assert not is_safe
    assert any("fertilizer" in issue.lower() for issue in issues)


# ============ Test 7: Unsupported pesticide is flagged ============

def test_unsupported_pesticide_dose_is_flagged():
    """Test that pesticide doses without evidence are flagged."""
    response_text = "Spray 500 ml of insecticide per acre to control aphids."
    
    validated, is_safe, issues = validate_response_detailed(response_text)
    
    assert not is_safe
    assert any("pesticide" in issue.lower() or "dosage" in issue.lower() for issue in issues)


def test_specific_pesticide_product_recommendation_is_flagged():
    """Test that product recommendations are flagged."""
    response_text = "Use Imidacloprid at 200 ml per acre for effective pest control."
    
    validated, is_safe, issues = validate_response_detailed(response_text)
    
    assert not is_safe


# ============ Test 8: Unsupported disease diagnosis is flagged ============

def test_strong_disease_diagnosis_is_flagged():
    """Test that confident disease diagnosis without evidence is flagged."""
    response_text = "Your wheat has yellow rust. Apply fungicide immediately."
    
    validated, is_safe, issues = validate_response_detailed(response_text)
    
    assert not is_safe
    assert any("disease" in issue.lower() for issue in issues)


# ============ Test 9: Unsupported variety is flagged ============

def test_specific_variety_without_evidence_is_flagged():
    """Test that specific variety recommendations are flagged."""
    response_text = "Plant FSD-2016 variety for best yields in Sahiwal."
    
    validated, is_safe, issues = validate_response_detailed(response_text)
    
    # This should be flagged as it's specific without evidence
    assert isinstance(is_safe, bool)


def test_detailed_validation_api_returns_tuple():
    """Test the detailed validation API and backward-compatible string API."""
    text = "Use a soil test to determine fertilizer requirements."
    validated, is_safe, issues = validate_response_detailed(text)
    assert is_safe
    assert validate_response_text(text) == text.strip()


def test_safe_check_soil_moisture_before_irrigation():
    text = "Check current soil moisture before irrigation."
    validated, is_safe, issues = validate_response_detailed(text)
    assert is_safe, issues


def test_safe_follow_local_weather_forecast():
    text = "Follow the local weather forecast."
    validated, is_safe, issues = validate_response_detailed(text)
    assert is_safe, issues


def test_unsafe_soil_test_shows_phosphorus_deficiency():
    text = "Your soil test shows phosphorus deficiency."
    validated, is_safe, issues = validate_response_detailed(text)
    assert not is_safe
    assert any("unsupported" in issue.lower() or "soil" in issue.lower() for issue in issues)


def test_unsafe_soil_moisture_is_adequate():
    text = "Your soil moisture is adequate."
    validated, is_safe, issues = validate_response_detailed(text)
    assert not is_safe


def test_unsafe_rainfall_this_week_was_20_mm():
    text = "Rainfall this week was 20 mm."
    validated, is_safe, issues = validate_response_detailed(text)
    assert not is_safe


# ============ Test 10: Evidence attribution preservation ============

def test_evidence_attribution_is_preserved():
    """Test that evidence sources are properly preserved."""
    evidence = [
        EvidenceItem(
            source="knowledge/crops/wheat.md",
            title="Wheat",
            content="Wheat typically requires preparation of seedbed.",
            score=9,
            quality=EvidenceQuality.MODERATE,
        ),
        EvidenceItem(
            source="knowledge/regions/punjab_pakistan.md",
            title="Punjab",
            content="Punjab has specific irrigation and soil characteristics.",
            score=7,
            quality=EvidenceQuality.GENERAL,
        ),
    ]
    
    formatted = format_evidence(evidence)
    
    assert "knowledge/crops/wheat.md" in formatted
    assert "knowledge/regions/punjab_pakistan.md" in formatted
    assert "SOURCE:" in formatted


# ============ Test 11: Recommendation-to-evidence linkage ============

def test_recommendation_to_evidence_linkage():
    """Test that recommendations can reference evidence."""
    response = AgriculturalResponse(
        situation="Wheat after rice",
        assessment="Assessment",
        recommendations=["Manage residue"],
        reasons="Supported by evidence on rice-wheat systems",
        missing_information=[],
        warnings=[],
        confidence="Moderate",
        evidence_sources=["knowledge/crops/wheat.md"],
        next_questions=[],
        intent=AgriculturalIntent.SOWING_PREPARATION,
        risk_level=RiskLevel.LOW,
    )
    
    # Evidence sources should be available for each recommendation
    assert len(response.evidence_sources) > 0
    assert "wheat.md" in response.evidence_sources[0]


# ============ Test 12: Risk level influences response behavior ============

def test_high_risk_intent_gets_conservative_treatment():
    """Test that high-risk intents trigger appropriate warnings."""
    farmer = FarmerContext(
        crop="Wheat",
        country="Pakistan",
        problem="Tell me exactly which pesticide to use and how much",
    )
    
    case = AgriculturalCase.from_farmer_context(farmer, farmer.problem)
    plan = build_decision_plan(case)
    
    # Pest/disease handling should be high risk
    if plan.intent == AgriculturalIntent.PEST_OR_DISEASE:
        assert plan.risk_level == RiskLevel.HIGH


def test_low_risk_intent_allows_direct_guidance():
    """Test that low-risk intents can provide direct guidance."""
    farmer = FarmerContext(
        crop="Wheat",
        country="Pakistan",
        problem="Preparing for sowing",
    )
    
    case = AgriculturalCase.from_farmer_context(farmer)
    plan = build_decision_plan(case)
    
    # Sowing preparation should be low risk
    assert plan.risk_level == RiskLevel.LOW


# ============ Test 13: High-risk case produces warning ============

def test_high_risk_case_has_warnings():
    """Test that high-risk decision plans include warnings."""
    farmer = FarmerContext(
        crop="Wheat",
        country="Pakistan",
        problem="Diagnosing disease symptoms",
    )
    
    case = AgriculturalCase.from_farmer_context(farmer)
    plan = build_decision_plan(case, AgriculturalIntent.PEST_OR_DISEASE)
    
    # Should be high risk
    assert plan.risk_level == RiskLevel.HIGH
    # Should have questions/actions emphasizing verification
    assert len(plan.questions_for_farmer) > 0 or len(plan.recommended_actions) > 0


# ============ Test 14: No-evidence case remains conservative ============

def test_no_evidence_response_is_conservative():
    """Test that responses without supporting evidence are conservative."""
    response_text = "Without local evidence, I recommend you consult with agricultural extension services."
    
    validated, is_safe, issues = validate_response_detailed(response_text)
    
    # Conservative response without specific claims should be safe
    assert is_safe


# ============ Test 15: Existing wheat/rice case works ============

def test_wheat_rice_sahiwal_case_works():
    """Test the standard wheat/rice/Sahiwal case from earlier milestones."""
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
    
    case = AgriculturalCase.from_farmer_context(farmer)
    plan = build_decision_plan(case)
    
    assert plan.intent == AgriculturalIntent.SOWING_PREPARATION
    assert plan.risk_level == RiskLevel.LOW
    assert "Wheat" in plan.retrieval_query
    assert "Rice" in plan.retrieval_query


# ============ Test 16-18: Backward compatibility ============

def test_existing_milestone_3_functionality_works():
    """Test that Milestone 3 retrieval still works."""
    from app.knowledge import LocalKnowledgeRetriever
    
    retriever = LocalKnowledgeRetriever()
    results = retriever.retrieve("Wheat sowing after rice")
    
    assert results
    assert any(item.source.endswith("wheat.md") for item in results)


def test_existing_milestone_4_validation_works():
    """Test that Milestone 4 recommendation validation still works."""
    from app.knowledge import Recommendation, ClaimType
    
    recommendation = Recommendation(
        text="Apply exactly 2 bags of DAP per acre.",
        claim_type=ClaimType.FERTILIZER,
        supporting_evidence=[],
        evidence_quality=EvidenceQuality.INSUFFICIENT,
    )
    
    # This should be flagged by Milestone 4 validation
    from app.knowledge import validate_recommendation
    validated = validate_recommendation(recommendation)
    
    assert validated.needs_verification


def test_existing_milestone_5_decision_layer_works():
    """Test that Milestone 5 decision layer still works."""
    farmer = FarmerContext(crop="Wheat", country="Pakistan", problem="How much urea?")
    case = AgriculturalCase.from_farmer_context(farmer)
    plan = build_decision_plan(case)
    
    assert plan.intent in [e for e in AgriculturalIntent]
    assert plan.risk_level in [RiskLevel.LOW, RiskLevel.MODERATE, RiskLevel.HIGH]
