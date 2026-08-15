from app.farmer_context import FarmerContext
from app.knowledge import LocalKnowledgeRetriever, load_knowledge_documents
from app.adviser import build_evidence_grounded_prompt


def test_farmer_context_can_be_created():
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

    assert context.crop == "Wheat"
    assert context.country == "Pakistan"
    assert context.district == "Sahiwal"


def test_knowledge_files_can_be_loaded():
    documents = load_knowledge_documents()

    assert documents
    assert any(doc.path.endswith("wheat.md") for doc in documents)


def test_wheat_knowledge_can_be_retrieved():
    retriever = LocalKnowledgeRetriever()
    results = retriever.retrieve("Wheat sowing preparation and residue management")

    assert results
    assert any(item.source.endswith("wheat.md") for item in results)


def test_wheat_rice_query_retrieves_wheat_evidence():
    retriever = LocalKnowledgeRetriever()
    results = retriever.retrieve("Wheat after rice in Sahiwal")

    assert results
    assert results[0].source.endswith("wheat.md")


def test_unrelated_query_does_not_receive_unjustifiably_high_wheat_score():
    retriever = LocalKnowledgeRetriever()
    results = retriever.retrieve("Repair a bicycle in the city")

    assert results == [] or all(item.score < 3 for item in results)


def test_evidence_objects_contain_source():
    retriever = LocalKnowledgeRetriever()
    results = retriever.retrieve("Wheat residue and rice-wheat system")

    assert results
    assert hasattr(results[0], "source")
    assert results[0].source.endswith("wheat.md")


def test_adviser_can_construct_an_evidence_grounded_prompt():
    context = FarmerContext(
        crop="Wheat",
        country="Pakistan",
        province="Punjab",
        district="Sahiwal",
        previous_crop="Rice",
        problem="Preparing for sowing",
    )
    evidence = [
        {
            "source": "knowledge/crops/wheat.md",
            "title": "Wheat general knowledge",
            "content": "Rice-wheat systems require attention to residue management, soil structure, and irrigation.",
            "score": 5,
        }
    ]

    prompt = build_evidence_grounded_prompt(context, evidence)

    assert "FARMER FACTS" in prompt
    assert "RETRIEVED EVIDENCE" in prompt
    assert "knowledge/crops/wheat.md" in prompt
    assert "evidence-grounded" in prompt.lower()


def test_adviser_can_work_with_missing_optional_farmer_information():
    context = FarmerContext(crop="Wheat", country="Pakistan")

    prompt = build_evidence_grounded_prompt(context, [])

    assert "Crop: Wheat" in prompt
    assert "Country: Pakistan" in prompt
    assert "No relevant evidence available" in prompt
