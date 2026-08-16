"""
Milestone 11 tests: Knowledge base productionization.

Deterministic tests (no network, no LLM, no external APIs) covering:
- schema validation
- provenance / source linkage
- content status
- farming-stage ranking
- applicability ranking (crop / district / province)
- placeholder handling
- version / supersession
- conflicts
- ingestion + schema validation on output
- deduplication
- batch ingestion
- safety regression
"""
from pathlib import Path

import pytest

from app.knowledge import (
    EvidenceItem,
    EvidenceQuality,
    LocalKnowledgeRetriever,
    load_knowledge_documents,
)
from app.knowledge_schema import validate_knowledge_metadata

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
FIXTURE_PDF = FIXTURE_DIR / "sample_official.pdf"


# ─── Fixtures: metadata used by pure schema tests (no filesystem) ────────────

VALID_EXTRACTED_METADATA = {
    "title": "Test Document",
    "content_status": "extracted",
    "source_id": "sahiwal-agriculture-extension",
    "document_id": "doc-1",
    "source_type": "official_extension",
    "version": "1.0",
    "status": "active",
    "evidence_quality": "general",
    "organization": "Test Organization",
    "last_updated": "2024-01-01",
}


# ─── Schema validation ───────────────────────────────────────────────────────

def test_schema_validator_accepts_valid_extracted_metadata():
    result = validate_knowledge_metadata(VALID_EXTRACTED_METADATA)
    assert result.is_valid is True
    assert result.errors == []


def test_schema_validator_rejects_missing_required_fields():
    result = validate_knowledge_metadata({"title": "Test"})
    assert result.is_valid is False
    assert any("Missing required field: content_status" in e for e in result.errors)


def test_placeholder_status_relaxed_validation():
    result = validate_knowledge_metadata({"title": "Placeholder", "content_status": "placeholder"})
    assert result.is_valid is True
    # Provenance gaps must be warnings, not fabricated or errors
    assert any("Missing recommended field" in w for w in result.warnings)


def test_extracted_requires_source_fields():
    metadata = dict(VALID_EXTRACTED_METADATA)
    metadata["document_id"] = ""
    result = validate_knowledge_metadata(metadata)
    assert result.is_valid is False
    assert any("document_id" in e and "Missing required" in e for e in result.errors)


def test_extracted_requires_trace_field():
    metadata = dict(VALID_EXTRACTED_METADATA)
    metadata["original_pdf_path"] = ""
    metadata["last_updated"] = ""
    metadata["published_date"] = ""
    result = validate_knowledge_metadata(metadata)
    assert result.is_valid is False
    assert any("at least one of" in e for e in result.errors)


def test_curated_requires_review_metadata():
    metadata = dict(VALID_EXTRACTED_METADATA)
    metadata["content_status"] = "curated"
    result = validate_knowledge_metadata(metadata)
    assert result.is_valid is False
    assert any("reviewed_by" in e for e in result.errors)
    assert any("review_date" in e for e in result.errors)


def test_schema_validator_rejects_invalid_enum():
    metadata = dict(VALID_EXTRACTED_METADATA)
    metadata["content_status"] = "not_a_status"
    result = validate_knowledge_metadata(metadata)
    assert result.is_valid is False
    assert any("Invalid value for content_status" in e for e in result.errors)


def test_schema_validator_rejects_invalid_date():
    metadata = dict(VALID_EXTRACTED_METADATA)
    metadata["last_updated"] = "not-a-date"
    result = validate_knowledge_metadata(metadata)
    assert result.is_valid is False
    assert any("Invalid date" in e for e in result.errors)


def test_schema_validator_rejects_unknown_source():
    metadata = dict(VALID_EXTRACTED_METADATA)
    metadata["source_id"] = "made-up-source"
    result = validate_knowledge_metadata(metadata)
    assert result.is_valid is False
    assert any("Unknown source_id" in e for e in result.errors)


def test_supersedes_terminology_warning():
    # "supersedes" means THIS document replaces an older one.
    metadata = dict(VALID_EXTRACTED_METADATA)
    metadata["status"] = "superseded"
    metadata["supersedes"] = "0.9"
    result = validate_knowledge_metadata(metadata)
    # Valid schema-wise, but the combination is semantically odd => warning.
    assert result.is_valid is True
    assert any("replaces an older version" in w for w in result.warnings)


# ─── Content status on the real knowledge base ───────────────────────────────

def test_existing_m3_docs_are_valid_placeholders():
    documents = load_knowledge_documents()
    by_path = {doc.path: doc for doc in documents}

    wheat = by_path["knowledge/crops/wheat.md"]
    punjab = by_path["knowledge/regions/punjab_pakistan.md"]

    assert wheat.metadata.get("content_status") == "placeholder"
    assert punjab.metadata.get("content_status") == "placeholder"

    wheat_result = validate_knowledge_metadata(wheat.metadata, wheat.path)
    punjab_result = validate_knowledge_metadata(punjab.metadata, punjab.path)
    assert wheat_result.is_valid is True
    assert punjab_result.is_valid is True


def test_m9_placeholders_still_valid():
    documents = load_knowledge_documents()
    by_path = {doc.path: doc for doc in documents}
    for path in ("knowledge/regions/sahiwal_punjab.md", "knowledge/topics/production_technology_guides.md"):
        doc = by_path[path]
        assert doc.metadata.get("content_status") == "placeholder"
        result = validate_knowledge_metadata(doc.metadata, doc.path)
        assert result.is_valid is True


# ─── Conflict detection (production-style evidence) ──────────────────────────

def test_conflict_detection_still_works_with_superseded_versions():
    from app.knowledge import detect_conflicts

    older = EvidenceItem(
        source="knowledge/topics/x.md",
        title="X",
        content="Rice residue should be burned before sowing.",
        score=8.0,
        quality=EvidenceQuality.MODERATE,
        document_version="1.1",
        document_id="x-doc",
    )
    newer = EvidenceItem(
        source="knowledge/topics/x_v2.md",
        title="X",
        content="Rice residue should not be burned before sowing.",
        score=9.0,
        quality=EvidenceQuality.MODERATE,
        document_version="1.2",
        document_id="x-doc",
    )
    conflicts = detect_conflicts([older, newer])
    assert any(c.conflict_type == "direct_contradiction" for c in conflicts)


# ─── Deterministic retrieval improvements (isolated temp knowledge base) ─────

def _write_doc(base: Path, rel: str, content: str) -> None:
    path = base / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _setup_temp_knowledge_base(tmp_path):
    """Build a small deterministic knowledge base and return the module patch pair."""
    import app.knowledge as knowledge

    knowledge_dir = tmp_path / "knowledge"
    _write_doc(knowledge_dir, "crops/wheat_guide.md", """---
title: Wheat Sowing Guide
document_id: wheat-guide
version: "2.0"
content_status: curated
source_type: official_extension
evidence_quality: strong
status: active
crop: wheat
region: Pakistan
province: Punjab
district: Sahiwal
farming_stage: sowing_preparation
organization: Test Agriculture Extension
last_updated: 2024-06-01
---
# Wheat Sowing Guide
Wheat sowing preparation requires a properly prepared seedbed with good
seed-to-soil contact. Verified official guidance for wheat sowing.
""")
    _write_doc(knowledge_dir, "crops/wheat_guide_old.md", """---
title: Wheat Sowing Guide (Old)
document_id: wheat-guide
version: "1.0"
content_status: curated
source_type: official_extension
evidence_quality: general
status: active
crop: wheat
region: Pakistan
province: Punjab
district: Sahiwal
farming_stage: sowing_preparation
organization: Test Agriculture Extension
last_updated: 2023-01-01
---
# Wheat Sowing Guide (Old)
Wheat sowing preparation guidance older version for reference.
""")
    _write_doc(knowledge_dir, "crops/wheat_irrigation.md", """---
title: Wheat Irrigation Guide
document_id: wheat-irrigation
version: "1.0"
content_status: curated
source_type: official_extension
evidence_quality: strong
status: active
crop: wheat
region: Pakistan
province: Punjab
district: Sahiwal
farming_stage: irrigation
organization: Test Agriculture Extension
last_updated: 2024-01-01
---
# Wheat Irrigation Guide
Wheat irrigation guidance based on soil moisture and crop water requirements.
""")
    _write_doc(knowledge_dir, "crops/rice_guide.md", """---
title: Rice Cultivation Guide
document_id: rice-guide
version: "1.0"
content_status: curated
source_type: official_extension
evidence_quality: strong
status: active
crop: rice
region: Pakistan
province: Punjab
district: Sahiwal
farming_stage: general_crop_advice
organization: Test Agriculture Extension
last_updated: 2024-01-01
---
# Rice Cultivation Guide
Rice cultivation agronomic guidance for local fields.
""")
    _write_doc(knowledge_dir, "topics/general_rice.md", """---
title: General Rice Note
document_id: general-rice-note
version: "1.0"
content_status: curated
source_type: agricultural_guidance
evidence_quality: general
status: active
crop: ""
region: Pakistan
farming_stage: general
organization: Test Advisor
last_updated: 2024-01-01
---
# General Rice Note
Rice cultivation guidance that applies generally across locations.
""")
    _write_doc(knowledge_dir, "crops/wheat_prod.md", """---
title: Wheat Production Guide
document_id: wheat-prod
version: "1.0"
content_status: curated
source_type: official_extension
evidence_quality: strong
status: active
crop: wheat
region: Pakistan
province: Punjab
farming_stage: general_crop_advice
organization: Test Agriculture Extension
last_updated: 2024-01-01
---
# Wheat Production Guide
Wheat production technology guidance for farmers.
""")
    _write_doc(knowledge_dir, "crops/wheat_prod_ph.md", """---
title: Wheat Production Guide Placeholder
document_id: wheat-prod-placeholder
version: "1.0"
content_status: placeholder
source_type: official_extension
evidence_quality: general
status: active
crop: wheat
region: Pakistan
province: Punjab
farming_stage: general_crop_advice
organization: Test Agriculture Extension
last_updated: 2024-01-01
---
# Wheat Production Guide Placeholder
Wheat production technology guidance for farmers.
""")
    _write_doc(knowledge_dir, "regions/sahiwal.md", """---
title: Sahiwal Regional Context
document_id: sahiwal-region
version: "1.0"
content_status: curated
source_type: agricultural_context
evidence_quality: general
status: active
crop: ""
region: Pakistan
province: Punjab
district: Sahiwal
farming_stage: general
organization: Sahiwal Extension
last_updated: 2024-01-01
---
# Sahiwal Regional Context
Wheat sowing context for the Sahiwal district area.
""")
    _write_doc(knowledge_dir, "regions/punjab.md", """---
title: Punjab Regional Context
document_id: punjab-region
version: "1.0"
content_status: curated
source_type: agricultural_context
evidence_quality: general
status: active
crop: ""
region: Pakistan
province: Punjab
farming_stage: general
organization: Punjab Extension
last_updated: 2024-01-01
---
# Punjab Regional Context
Wheat sowing context for the province of Punjab more broadly.
""")
    _write_doc(knowledge_dir, "topics/bike_notes.md", """---
title: Unrelated Notes
document_id: unrelated-notes
version: "1.0"
content_status: placeholder
source_type: agricultural_context
evidence_quality: insufficient
status: active
farming_stage: general
organization: Test Advisor
last_updated: 2024-01-01
---
# Unrelated Notes
Bicycle repair shop notes unrelated to agriculture.
""")

    return knowledge_dir


@pytest.fixture
def temp_retriever(monkeypatch, tmp_path):
    import app.knowledge as knowledge

    knowledge_dir = _setup_temp_knowledge_base(tmp_path)
    monkeypatch.setattr(knowledge, "KNOWLEDGE_DIR", knowledge_dir)
    monkeypatch.setattr(knowledge, "PROJECT_ROOT", tmp_path)
    return LocalKnowledgeRetriever()


def _document_ids(results):
    return [r.document_id for r in results]


def test_farming_stage_boost_ranks_matching_stage_first(temp_retriever):
    results = temp_retriever.retrieve("wheat sowing", top_k=5)
    ids = _document_ids(results)
    assert "wheat-guide" in ids  # farming_stage = sowing_preparation
    sowing_idx = ids.index("wheat-guide") if "wheat-guide" in ids else 99
    irrigation_idx = ids.index("wheat-irrigation") if "wheat-irrigation" in ids else -1
    assert sowing_idx < irrigation_idx


def test_crop_specific_preferred_over_multi_crop(temp_retriever):
    results = temp_retriever.retrieve("rice", top_k=5)
    ids = _document_ids(results)
    assert "rice-guide" in ids
    assert "general-rice-note" in ids
    assert ids.index("rice-guide") < ids.index("general-rice-note")


def test_district_preferred_over_province(temp_retriever):
    results = temp_retriever.retrieve("wheat sowing sahiwal", top_k=10)
    ids = _document_ids(results)
    sahiwal_idx = ids.index("sahiwal-region") if "sahiwal-region" in ids else 99
    punjab_idx = ids.index("punjab-region") if "punjab-region" in ids else 99
    assert sahiwal_idx < punjab_idx


def test_supersession_prefers_newest_version(temp_retriever):
    results = temp_retriever.retrieve("wheat guide", top_k=10)
    wheat_guide_items = [r for r in results if r.document_id == "wheat-guide"]
    assert len(wheat_guide_items) == 1
    assert wheat_guide_items[0].document_version == "2.0"


def test_placeholder_penalized_below_curated(temp_retriever):
    results = temp_retriever.retrieve("wheat production", top_k=5)
    ids = _document_ids(results)
    assert "wheat-prod" in ids
    assert "wheat-prod-placeholder" in ids
    assert ids.index("wheat-prod") < ids.index("wheat-prod-placeholder")


def test_irrelevant_placeholder_not_returned_as_evidence(temp_retriever):
    results = temp_retriever.retrieve("wheat production", top_k=5)
    assert "unrelated-notes" not in _document_ids(results)


# ─── Ingestion: schema validation on output, dedup, batch ────────────────────

def _monkeypatch_registry(monkeypatch, tmp_path):
    """Point the source registry at a temp dir with a known Sahiwal source."""
    import app.source_registry as source_registry

    registry_dir = tmp_path / "registry"
    registry_dir.mkdir(parents=True, exist_ok=True)
    (registry_dir / "sahiwal_agriculture_extension.json").write_text(
        '{"source_id": "sahiwal-agriculture-extension", "title": "Sahiwal Agriculture Extension", '
        '"organization": "Agriculture Extension Department, Sahiwal", '
        '"source_type": "official_extension", "status": "registered", "document_path": ""}',
        encoding="utf-8",
    )
    monkeypatch.setattr(source_registry, "REGISTRY_DIR", registry_dir)
    return registry_dir


def test_conversion_output_passes_schema(tmp_path, monkeypatch):
    from app.document_metadata import build_document_metadata
    from app.knowledge_converter import convert_to_knowledge_markdown
    from app.pdf_extractor import extract_pdf_text

    _monkeypatch_registry(monkeypatch, tmp_path)

    metadata = build_document_metadata(
        source_id="sahiwal-agriculture-extension",
        document_id="sahiwal-wheat-guide-2024",
        title="Sahiwal Wheat Production Guide",
        original_pdf_path=str(FIXTURE_PDF),
    )
    extraction = extract_pdf_text(FIXTURE_PDF)
    output = convert_to_knowledge_markdown(extraction, metadata)

    from app.knowledge import parse_front_matter

    parsed, _ = parse_front_matter(output.markdown)
    result = validate_knowledge_metadata(parsed)
    assert result.is_valid is True
    assert output.metadata.get("content_status") == "extracted"
    assert output.metadata.get("organization") == "Agriculture Extension Department, Sahiwal"


def test_conversion_rejects_incomplete_metadata(tmp_path, monkeypatch):
    from app.document_metadata import DocumentMetadata
    from app.knowledge_converter import convert_to_knowledge_markdown
    from app.pdf_extractor import extract_pdf_text

    _monkeypatch_registry(monkeypatch, tmp_path)

    metadata = DocumentMetadata(
        source_id="sahiwal-agriculture-extension",
        document_id="doc-1",
        title="Test",
        original_pdf_path=str(FIXTURE_PDF),
        version="",
        organization="",
    )
    extraction = extract_pdf_text(FIXTURE_PDF)
    with pytest.raises(ValueError, match="schema validation"):
        convert_to_knowledge_markdown(extraction, metadata)


def test_ingest_dedup_blocks_duplicate_document_id(tmp_path, monkeypatch):
    from app.ingestion import ingest_pdf

    _monkeypatch_registry(monkeypatch, tmp_path)
    target = tmp_path / "out"

    first = ingest_pdf(
        pdf_path=FIXTURE_PDF,
        source_id="sahiwal-agriculture-extension",
        document_id="sahiwal-wheat-guide-2024",
        title="Sahiwal Wheat Production Guide",
        target_dir=target,
    )
    assert first.success is True

    second = ingest_pdf(
        pdf_path=FIXTURE_PDF,
        source_id="sahiwal-agriculture-extension",
        document_id="sahiwal-wheat-guide-2024",
        title="Sahiwal Wheat Production Guide (again)",
        target_dir=target,
    )
    assert second.success is False
    assert any("Duplicate" in i for i in second.issues)


def test_batch_ingestion_reports_per_document_results(tmp_path, monkeypatch):
    from app.ingestion import ingest_pdfs

    _monkeypatch_registry(monkeypatch, tmp_path)
    target = tmp_path / "out"

    batch = ingest_pdfs(
        items=[
            {
                "pdf_path": str(FIXTURE_PDF),
                "source_id": "sahiwal-agriculture-extension",
                "document_id": "batch-doc-1",
                "title": "Batch Document One",
            },
            {
                "pdf_path": str(FIXTURE_DIR / "missing.pdf"),
                "source_id": "sahiwal-agriculture-extension",
                "document_id": "batch-doc-2",
                "title": "Batch Document Two",
            },
        ],
        target_dir=target,
    )

    assert batch.total == 2
    assert batch.succeeded == 1
    assert batch.failed == 1
    assert batch.results[0].success is True
    assert batch.results[1].success is False


# ─── Safety regression ───────────────────────────────────────────────────────

def test_pesticide_safety_still_flagged():
    from app.adviser import validate_response_detailed

    validated, is_safe, issues = validate_response_detailed(
        "Spray 500 ml/acre of insecticide to control aphids."
    )
    assert is_safe is False
    assert any("pesticide" in i.lower() or "dosage" in i.lower() for i in issues)


def test_recommendation_dict_evidence_still_flagged():
    from app.knowledge import ClaimType, Recommendation, validate_recommendation

    recommendation = Recommendation(
        text="Spray 500 ml/acre of pesticide X.",
        claim_type=ClaimType.PESTICIDE,
        supporting_evidence=[
            {
                "source": "knowledge/crops/wheat.md",
                "title": "Wheat",
                "content": "Pesticides should only be used according to the locally registered product label.",
                "score": 8,
                "quality": "moderate",
            }
        ],
        evidence_quality=EvidenceQuality.MODERATE,
        confidence="medium",
        needs_verification=False,
    )
    validated = validate_recommendation(recommendation)
    assert validated.needs_verification is True
    assert validated.warning is not None