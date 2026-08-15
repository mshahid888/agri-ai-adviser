"""
Milestone 9 tests: Official Agricultural Knowledge Base & Source Registry.

Tests verify the source registry, official source metadata, provenance
linkage, Markdown retrieval, local/district metadata, unrelated-query
rejection, and registry validation.
"""
from app.knowledge import LocalKnowledgeRetriever, load_knowledge_documents
from app.source_registry import (
    SourceRecord,
    get_source,
    list_sources,
    load_source_registry,
    validate_source_record,
)

EXPECTED_SOURCE_IDS = {
    "sahiwal-agriculture-extension",
    "punjab-agriculture-extension",
    "sahiwal-soil-water-testing-lab",
    "potato-research-institute-sahiwal",
    "maize-millets-research-institute-yusafwala",
}

NEW_KNOWLEDGE_PATHS = {
    "knowledge/regions/sahiwal_punjab.md",
    "knowledge/crops/rice.md",
    "knowledge/topics/production_technology_guides.md",
}


# ============ Source registry ============

def test_source_registry_loads_expected_official_sources():
    records = load_source_registry()
    source_ids = {record.source_id for record in records}

    assert EXPECTED_SOURCE_IDS.issubset(source_ids)


def test_source_record_has_required_fields():
    for record in load_source_registry():
        assert record.source_id
        assert record.title
        assert record.organization
        assert record.source_type
        assert record.status


def test_verified_sources_have_official_url():
    for record in load_source_registry():
        if record.url_status == "verified":
            assert record.official_url, f"{record.source_id} is verified but has no URL"
        else:
            assert record.url_status == "pending_verification"


def test_registry_files_are_not_loaded_as_knowledge_documents():
    documents = load_knowledge_documents()
    registry_paths = [doc.path for doc in documents if "sources/registry/" in doc.path]

    assert registry_paths == []


# ============ Provenance linkage ============

def test_knowledge_document_links_to_source_via_source_id():
    documents = load_knowledge_documents()
    registry_ids = {record.source_id for record in load_source_registry()}

    for doc in documents:
        if doc.path in NEW_KNOWLEDGE_PATHS:
            source_id = doc.metadata.get("source_id")
            assert source_id, f"{doc.path} is missing source_id"
            assert source_id in registry_ids, f"{doc.path} links to unknown source {source_id}"


def test_knowledge_placeholders_are_marked_non_substantive():
    documents = load_knowledge_documents()

    for doc in documents:
        if doc.path in NEW_KNOWLEDGE_PATHS:
            assert doc.metadata.get("content_status") == "placeholder"


def test_new_knowledge_documents_load_with_provenance():
    documents = load_knowledge_documents()
    by_path = {doc.path: doc for doc in documents}

    sahiwal = by_path["knowledge/regions/sahiwal_punjab.md"]
    assert sahiwal.provenance is not None
    assert sahiwal.provenance.organization == "Agriculture Extension Department, Sahiwal"
    assert sahiwal.provenance.source_type == "agricultural_context"
    assert sahiwal.version_info is not None
    assert sahiwal.version_info.version == "1.0"

    rice = by_path["knowledge/crops/rice.md"]
    assert rice.provenance is not None
    assert rice.provenance.organization == "Agriculture Extension Department, Government of Punjab"
    assert rice.provenance.source_type == "agricultural_guidance"


# ============ Retrieval ============

def test_relevant_query_retrieves_new_knowledge():
    retriever = LocalKnowledgeRetriever()
    results = retriever.retrieve("Sahiwal regional agricultural")

    assert results
    assert any(item.source.endswith("sahiwal_punjab.md") for item in results)


def test_unrelated_query_returns_nothing():
    retriever = LocalKnowledgeRetriever()
    results = retriever.retrieve("bicycle repair")

    assert results == []


# ============ Registry validation ============

def test_source_registry_validation_flags_missing_required_fields():
    invalid = SourceRecord(
        source_id="",
        title="",
        organization="",
        source_type="",
        status="",
    )
    issues = validate_source_record(invalid)

    assert any("source_id" in issue for issue in issues)
    assert any("title" in issue for issue in issues)
    assert any("organization" in issue for issue in issues)
    assert any("source_type" in issue for issue in issues)
    assert any("status" in issue for issue in issues)


def test_source_registry_validation_passes_for_valid_record():
    valid = SourceRecord(
        source_id="test-source",
        title="Test Source",
        organization="Test Organization",
        source_type="official_extension",
        status="registered",
    )
    issues = validate_source_record(valid)

    assert issues == []