from app.knowledge import (
    KnowledgeDocument,
    LocalKnowledgeRetriever,
    load_knowledge_documents,
    parse_front_matter,
)


def test_front_matter_parsing():
    markdown = '''---
title: Wheat
crop: wheat
region: Pakistan
province: Punjab
topic: crop_management
source_type: agricultural_guidance
evidence_quality: moderate
---

# Wheat

Wheat is a Rabi crop.
'''
    metadata, body = parse_front_matter(markdown)

    assert metadata["title"] == "Wheat"
    assert metadata["crop"] == "wheat"
    assert metadata["province"] == "Punjab"
    assert "Wheat is a Rabi crop." in body


def test_markdown_without_front_matter_still_loads():
    markdown = "# Plain note\n\nThis is normal markdown without metadata."
    metadata, body = parse_front_matter(markdown)

    assert metadata == {}
    assert "This is normal markdown without metadata." in body


def test_metadata_is_preserved():
    document = KnowledgeDocument(
        path="knowledge/crops/wheat.md",
        title="Wheat",
        content="Wheat content",
        metadata={
            "crop": "wheat",
            "province": "Punjab",
            "topic": "crop_management",
        },
    )

    assert document.metadata["crop"] == "wheat"
    assert document.metadata["province"] == "Punjab"
    assert document.title == "Wheat"


def test_knowledge_document_remains_backward_compatible():
    document = KnowledgeDocument(
        path="knowledge/crops/wheat.md",
        title="Wheat",
        content="Wheat content",
    )

    assert document.path == "knowledge/crops/wheat.md"
    assert document.title == "Wheat"
    assert document.content == "Wheat content"
    assert document.metadata == {}


def test_metadata_contributes_to_retrieval_relevance():
    retriever = LocalKnowledgeRetriever()
    results = retriever.retrieve("Wheat fertilizer management in Punjab")

    assert results
    wheat_match = any(item.source.endswith("wheat.md") for item in results)
    punjab_match = any(item.source.endswith("punjab_pakistan.md") for item in results)
    assert wheat_match or punjab_match


def test_unrelated_query_returns_no_relevant_results():
    retriever = LocalKnowledgeRetriever()
    results = retriever.retrieve("Repair a bicycle in the city")

    assert results == []


def test_wheat_query_returns_wheat_document():
    retriever = LocalKnowledgeRetriever()
    results = retriever.retrieve("Wheat sowing after rice")

    assert results
    assert any(item.source.endswith("wheat.md") for item in results)
    assert results[0].source.endswith("wheat.md")


def test_punjab_wheat_query_gets_metadata_boost_without_ignoring_content():
    retriever = LocalKnowledgeRetriever()
    wheat_results = retriever.retrieve("Wheat in Punjab")
    generic_results = retriever.retrieve("Wheat")

    assert wheat_results
    assert any(item.source.endswith("wheat.md") for item in wheat_results)
    wheat_item = next(item for item in wheat_results if item.source.endswith("wheat.md"))
    generic_item = next(item for item in generic_results if item.source.endswith("wheat.md"))
    assert wheat_item.score >= generic_item.score


def test_metadata_alone_cannot_make_unrelated_document_relevant():
    retriever = LocalKnowledgeRetriever()
    results = retriever.retrieve("Bicycle repair in Punjab")

    assert results == []


def test_missing_metadata_does_not_crash_retrieval():
    retriever = LocalKnowledgeRetriever()
    results = retriever.retrieve("Crop management advice")

    assert isinstance(results, list)


def test_provenance_is_parsed_from_front_matter():
    markdown = '''---
title: Wheat
crop: wheat
region: Pakistan
version: "1.2"
last_updated: "2024-06-01"
status: "active"
reviewed_by: "local agronomy review"
review_date: "2024-06-01"
author: "Agricultural Knowledge Team"
organization: "Local Extension Advisory"
notes: "General agronomic guidance"
---

# Wheat

Wheat is a Rabi crop.
'''
    metadata, _ = parse_front_matter(markdown)
    doc = KnowledgeDocument(
        path="knowledge/crops/wheat.md",
        title="Wheat",
        content="Wheat is a Rabi crop.",
        metadata=metadata,
    )

    assert doc.metadata["version"] == "1.2"
    assert doc.metadata["last_updated"] == "2024-06-01"
    assert doc.metadata["status"] == "active"


def test_missing_provenance_metadata_remains_backward_compatible():
    doc = KnowledgeDocument(
        path="knowledge/crops/wheat.md",
        title="Wheat",
        content="Wheat content",
        metadata={"crop": "wheat"},
    )

    assert doc.provenance is None
    assert doc.version_info is None


def test_version_and_freshness_metadata_are_loaded():
    documents = load_knowledge_documents()
    wheat_doc = next(doc for doc in documents if doc.path.endswith("wheat.md"))

    assert wheat_doc.version_info is not None
    assert wheat_doc.version_info.version == "1.2"
    assert wheat_doc.version_info.status == "active"
    assert wheat_doc.provenance is not None
    assert wheat_doc.provenance.source_type == "agricultural_guidance"


def test_supersession_is_detected_as_advisory_conflict():
    from app.knowledge import detect_conflicts, EvidenceItem, EvidenceQuality

    older = EvidenceItem(
        source="knowledge/crops/wheat_old.md",
        title="Wheat",
        content="Rice residue should be burned before sowing.",
        score=8.0,
        quality=EvidenceQuality.MODERATE,
        document_version="1.1",
    )
    newer = EvidenceItem(
        source="knowledge/crops/wheat.md",
        title="Wheat",
        content="Rice residue should not be burned before sowing.",
        score=9.0,
        quality=EvidenceQuality.MODERATE,
        document_version="1.2",
    )

    conflicts = detect_conflicts([older, newer])
    assert conflicts
    assert any(record.conflict_type == "direct_contradiction" for record in conflicts)


def test_conflict_remains_non_blocking():
    from app.knowledge import detect_conflicts, EvidenceItem, EvidenceQuality

    left = EvidenceItem(
        source="knowledge/crops/wheat.md",
        title="Wheat",
        content="Rice residue should not be burned before sowing.",
        score=9.0,
        quality=EvidenceQuality.MODERATE,
        document_version="1.2",
    )
    right = EvidenceItem(
        source="knowledge/crops/wheat_old.md",
        title="Wheat",
        content="Rice residue can be burned before sowing.",
        score=8.0,
        quality=EvidenceQuality.MODERATE,
        document_version="1.1",
    )

    conflicts = detect_conflicts([left, right])
    assert conflicts
    assert len(conflicts) >= 1


def test_provenance_cannot_trigger_relevance():
    retriever = LocalKnowledgeRetriever()
    results = retriever.retrieve("Bicycle repair in Punjab")

    assert results == []


def test_freshness_metadata_cannot_trigger_relevance():
    retriever = LocalKnowledgeRetriever()
    results = retriever.retrieve("Bike repair with version 1.2")

    assert results == []


def test_metadata_boost_still_works_for_relevant_agricultural_queries():
    retriever = LocalKnowledgeRetriever()
    results = retriever.retrieve("Wheat fertilizer management in Punjab")

    assert results
    assert any(item.source.endswith("wheat.md") for item in results)
    assert any(item.source.endswith("punjab_pakistan.md") for item in results)


def test_general_agronomic_guidance_is_not_flagged_as_unsupported_measurement():
    from app.adviser import validate_response_detailed

    response = (
        "Ensure adequate soil moisture for germination. "
        "Rice cultivation can affect soil structure. "
        "Good seed-to-soil contact supports establishment. "
        "Manage rice residue before sowing. "
        "Use a soil test to determine fertilizer requirements."
    )

    validated, is_safe, issues = validate_response_detailed(response)
    assert is_safe is True
    assert issues == []


def test_unsupported_field_measurement_is_still_flagged():
    from app.adviser import validate_response_detailed

    response = "Your soil moisture is adequate and rainfall this week was 20 mm."
    validated, is_safe, issues = validate_response_detailed(response)

    assert is_safe is False
    assert any("unsupported claims" in issue.lower() or "unsupported" in issue.lower() for issue in issues)


def test_existing_content_retrieval_still_works():
    retriever = LocalKnowledgeRetriever()
    results = retriever.retrieve("Wheat sowing after rice")

    assert results
    assert any(item.source.endswith("wheat.md") for item in results)


def test_source_path_is_preserved():
    documents = load_knowledge_documents()
    assert any(doc.path.endswith("wheat.md") for doc in documents)
    assert any(doc.path.endswith("punjab_pakistan.md") for doc in documents)


def test_wheat_document_loads_correctly():
    documents = load_knowledge_documents()
    wheat_doc = next(doc for doc in documents if doc.path.endswith("wheat.md"))

    assert wheat_doc.title == "Wheat"
    assert "Wheat is a Rabi-season cereal crop." in wheat_doc.content
    assert wheat_doc.metadata.get("crop") == "wheat"


def test_punjab_document_loads_correctly():
    documents = load_knowledge_documents()
    punjab_doc = next(doc for doc in documents if doc.path.endswith("punjab_pakistan.md"))

    assert punjab_doc.title == "Punjab, Pakistan"
    assert "Punjab is a major agricultural region of Pakistan" in punjab_doc.content
    assert punjab_doc.metadata.get("province") == "Punjab"


def test_existing_milestone_3_tests_still_pass():
    documents = load_knowledge_documents()
    assert documents
    assert any(doc.path.endswith("wheat.md") for doc in documents)


def test_existing_milestone_4_tests_still_pass():
    from app.knowledge import Recommendation, ClaimType, EvidenceQuality, validate_recommendation

    recommendation = Recommendation(
        text="Apply exactly 2 bags of DAP per acre.",
        claim_type=ClaimType.FERTILIZER,
        supporting_evidence=[],
        evidence_quality=EvidenceQuality.INSUFFICIENT,
        confidence="medium",
        needs_verification=False,
    )
    validated = validate_recommendation(recommendation)
    assert validated.needs_verification is True


def test_existing_milestone_5_tests_still_pass():
    from app.adviser import AgriculturalCase, AgriculturalIntent, RiskLevel, build_decision_plan
    from app.farmer_context import FarmerContext

    farmer = FarmerContext(crop="Wheat", country="Pakistan", problem="How much urea?")
    case = AgriculturalCase.from_farmer_context(farmer)
    plan = build_decision_plan(case)

    assert plan.intent in [e for e in AgriculturalIntent]
    assert plan.risk_level in [RiskLevel.LOW, RiskLevel.MODERATE, RiskLevel.HIGH]


def test_existing_milestone_6_tests_still_pass():
    from app.adviser import AgriculturalResponse, AgriculturalIntent, RiskLevel

    response = AgriculturalResponse(
        situation="Wheat after rice",
        assessment="Assessment",
        recommendations=["Prepare seedbed"],
        reasons="Good practice",
        missing_information=[],
        warnings=[],
        confidence="Moderate",
        evidence_sources=["knowledge/crops/wheat.md"],
        next_questions=[],
        intent=AgriculturalIntent.SOWING_PREPARATION,
        risk_level=RiskLevel.LOW,
    )

    assert response.to_farmer_text()
    assert response.intent == AgriculturalIntent.SOWING_PREPARATION
