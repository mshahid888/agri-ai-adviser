"""
M14 + M15 Implementation Tests.
Covers persistent memory, feedback, multimodal vision, and integrated agent flow.
"""
import os
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.memory import MemoryRepository, FarmerProfile, FarmerMemory, Session, Interaction
from app.context_manager import ContextManager
from app.farmer_context import FarmerContext
from app.vision import VisionAnalyzer, VisionResult
from app.feedback import record_feedback, get_average_rating


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def db(tmp_path):
    """Provide a MemoryRepository backed by a temporary database."""
    repo = MemoryRepository(db_path=str(tmp_path / "test.db"))
    yield repo
    repo.close()


@pytest.fixture
def mock_vision():
    """Mock VisionAnalyzer to avoid actual API calls."""
    class MockVisionAnalyzer(VisionAnalyzer):
        def __init__(self):
            self.enabled = True
        def validate_image(self, image_path: str) -> bool:
            return os.path.exists(image_path)
        def analyze(self, image_path: str, query: str = "") -> VisionResult:
            return VisionResult(
                observations=["Yellowing between leaf veins", "Possible lesion on lower leaf"],
                candidates=["Nutrient deficiency", "Early blight", "Water stress"],
                confidence=0.75,
                uncertainty="Image resolution is low; cannot confirm disease type",
                limitations="Cannot determine soil conditions or history from image alone",
            )
    return MockVisionAnalyzer()


# ─── M14: Memory Repository ─────────────────────────────────────────────────

def test_farmer_profile_create_and_retrieve(db):
    profile = FarmerProfile(farmer_id="f1", name="Ali", crop="Wheat", province="Punjab")
    db.upsert_farmer(profile)
    retrieved = db.get_farmer("f1")
    assert retrieved is not None
    assert retrieved.name == "Ali"
    assert retrieved.crop == "Wheat"
    assert retrieved.province == "Punjab"


def test_farmer_profile_update(db):
    db.upsert_farmer(FarmerProfile(farmer_id="f1", crop="Wheat"))
    db.upsert_farmer(FarmerProfile(farmer_id="f1", crop="Rice"))
    retrieved = db.get_farmer("f1")
    assert retrieved.crop == "Rice"


def test_farmer_not_found_returns_none(db):
    assert db.get_farmer("nonexistent") is None


def test_memory_add_and_retrieve(db):
    mem = FarmerMemory(memory_id="m1", farmer_id="f1", memory_type="profile", content="Grows wheat on 3 hectares")
    db.add_memory(mem)
    memories = db.get_memories("f1")
    assert len(memories) == 1
    assert memories[0].content == "Grows wheat on 3 hectares"


def test_memory_type_filter(db):
    db.add_memory(FarmerMemory(memory_id="m1", farmer_id="f1", memory_type="profile", content="Profile info"))
    db.add_memory(FarmerMemory(memory_id="m2", farmer_id="f1", memory_type="interaction", content="Interaction info"))
    assert len(db.get_memories("f1", memory_type="profile")) == 1
    assert db.get_memories("f1", memory_type="profile")[0].content == "Profile info"


def test_memory_relevance_filter(db):
    db.add_memory(FarmerMemory(memory_id="m1", farmer_id="f1", memory_type="profile", content="High", relevance_score=0.9))
    db.add_memory(FarmerMemory(memory_id="m2", farmer_id="f1", memory_type="profile", content="Low", relevance_score=0.1))
    results = db.get_memories("f1", min_relevance=0.5)
    assert len(results) == 1
    assert results[0].content == "High"


def test_memory_keyword_search(db):
    db.add_memory(FarmerMemory(memory_id="m1", farmer_id="f1", memory_type="interaction", content="Yellow leaves on wheat"))
    db.add_memory(FarmerMemory(memory_id="m2", farmer_id="f1", memory_type="interaction", content="Sowing rice in Sahiwal"))
    results = db.search_memories("f1", ["yellow", "wheat"])
    assert len(results) == 1
    assert "yellow" in results[0].content.lower()


def test_memory_limit(db):
    for i in range(10):
        db.add_memory(FarmerMemory(memory_id=f"m{i}", farmer_id="f1", memory_type="interaction", content=f"Memory {i}"))
    assert len(db.get_memories("f1", limit=3)) == 3


def test_memory_no_duplicates_on_replace(db):
    db.add_memory(FarmerMemory(memory_id="m1", farmer_id="f1", memory_type="profile", content="V1"))
    db.add_memory(FarmerMemory(memory_id="m1", farmer_id="f1", memory_type="profile", content="V2"))
    results = db.get_memories("f1")
    assert len(results) == 1
    assert results[0].content == "V2"


# ─── M14: Interactions ──────────────────────────────────────────────────────

def test_interaction_persistence(db):
    interaction = Interaction(
        interaction_id="i1", farmer_id="f1", session_id="s1",
        query="When to sow wheat?", response="November is typical.", intent="sowing_preparation",
    )
    db.add_interaction(interaction)
    results = db.get_interactions("f1")
    assert len(results) == 1
    assert results[0].query == "When to sow wheat?"


def test_interaction_limit(db):
    for i in range(10):
        db.add_interaction(Interaction(
            interaction_id=f"i{i}", farmer_id="f1", session_id="s1",
            query=f"Q{i}", response=f"A{i}", intent="general",
        ))
    assert len(db.get_interactions("f1", limit=3)) == 3


# ─── M14: Session Persistence ───────────────────────────────────────────────

def test_session_persistence(db):
    session = Session(session_id="s1", farmer_id="f1", state_json=json.dumps({"crop": "Rice"}))
    db.upsert_session(session)
    retrieved = db.get_session("s1")
    assert retrieved is not None
    assert json.loads(retrieved.state_json)["crop"] == "Rice"


def test_session_not_found(db):
    assert db.get_session("nonexistent") is None


def test_session_upsert_replaces(db):
    db.upsert_session(Session(session_id="s1", farmer_id="f1", state_json=json.dumps({"crop": "Wheat"})))
    db.upsert_session(Session(session_id="s1", farmer_id="f1", state_json=json.dumps({"crop": "Rice"})))
    s = db.get_session("s1")
    assert json.loads(s.state_json)["crop"] == "Rice"


# ─── M14: Context Persistence ───────────────────────────────────────────────

def test_context_persistence(db):
    db.save_context("sess1", {"crop": "Maize", "country": "Pakistan"})
    data = db.get_context("sess1")
    assert data is not None
    assert data["crop"] == "Maize"


def test_context_not_found(db):
    assert db.get_context("nonexistent") is None


def test_context_upsert(db):
    db.save_context("sess1", {"crop": "Wheat"})
    db.save_context("sess1", {"crop": "Rice"})
    data = db.get_context("sess1")
    assert data["crop"] == "Rice"


# ─── M14: Feedback ──────────────────────────────────────────────────────────

def test_feedback_save_and_retrieve(db):
    db.save_feedback("i1", 4, "Good advice")
    fb = db.get_feedback("i1")
    assert fb is not None
    assert fb["rating"] == 4
    assert fb["comment"] == "Good advice"


def test_feedback_aggregation(db):
    db.save_feedback("i1", 5, "Excellent")
    db.save_feedback("i2", 3, "OK")
    stats = db.get_feedback_stats()
    assert stats["total_feedback"] == 2
    assert abs(stats["average_rating"] - 4.0) < 0.01


def test_feedback_rejects_invalid_rating(db):
    with pytest.raises(ValueError, match="Rating must be between 1 and 5"):
        db.save_feedback("i1", 6, "Too high")


def test_feedback_stats_empty(db):
    stats = db.get_feedback_stats()
    assert stats["total_feedback"] == 0
    assert stats["average_rating"] == 0.0


# ─── M14: ContextManager Integration ────────────────────────────────────────

def test_context_manager_creates_and_persists(db):
    ctx_mgr = ContextManager(memory=db)
    ctx = ctx_mgr.get_or_create_context("session_123", {"crop": "Maize", "district": "Lahore"})
    assert ctx.crop == "Maize"
    assert ctx.district == "Lahore"

    # New ContextManager instance simulates app restart
    ctx_mgr_2 = ContextManager(memory=db)
    ctx2 = ctx_mgr_2.get_or_create_context("session_123")
    assert ctx2 is not None
    assert ctx2.crop == "Maize"
    assert ctx2.district == "Lahore"


def test_context_manager_merge_existing(db):
    ctx_mgr = ContextManager(memory=db)
    ctx1 = ctx_mgr.get_or_create_context("s1", {"crop": "Wheat", "province": "Punjab"})
    ctx2 = ctx_mgr.get_or_create_context("s1", {"district": "Sahiwal"})
    assert ctx2.crop == "Wheat"
    assert ctx2.district == "Sahiwal"


def test_context_manager_without_memory():
    ctx_mgr = ContextManager()
    ctx = ctx_mgr.get_or_create_context("s1", {"crop": "Rice"})
    assert ctx.crop == "Rice"
    ctx2 = ctx_mgr.get_or_create_context("s1")
    assert ctx2.crop == "Rice"


def test_context_manager_clear_session(db):
    ctx_mgr = ContextManager(memory=db)
    ctx_mgr.get_or_create_context("s1", {"crop": "Wheat"})
    assert ctx_mgr.clear_session("s1") is True
    assert ctx_mgr._sessions.get("s1") is None


# ─── M14: Memory Search Relevance ───────────────────────────────────────────

def test_search_memories_returns_relevant(db):
    db.add_memory(FarmerMemory(memory_id="m1", farmer_id="f1", memory_type="interaction", content="Yellow leaves on wheat"))
    db.add_memory(FarmerMemory(memory_id="m2", farmer_id="f1", memory_type="interaction", content="Sowing rice"))
    results = db.search_memories("f1", ["wheat", "yellow"])
    assert len(results) >= 1
    assert any("wheat" in r.content.lower() for r in results)


def test_search_memories_empty_keywords_falls_back(db):
    db.add_memory(FarmerMemory(memory_id="m1", farmer_id="f1", memory_type="interaction", content="General note"))
    results = db.search_memories("f1", [])
    assert len(results) == 1


# ─── M15: Vision Validation ─────────────────────────────────────────────────

def test_vision_rejects_missing_image():
    analyzer = VisionAnalyzer()
    assert analyzer.validate_image("nonexistent.jpg") is False


def test_vision_rejects_wrong_extension(tmp_path):
    bad_file = tmp_path / "notes.txt"
    bad_file.write_text("not an image", encoding="utf-8")
    analyzer = VisionAnalyzer()
    assert analyzer.validate_image(str(bad_file)) is False


def test_vision_rejects_oversized_image(tmp_path):
    big_file = tmp_path / "big.jpg"
    big_file.write_bytes(b"\xff" * (11 * 1024 * 1024))
    analyzer = VisionAnalyzer()
    assert analyzer.validate_image(str(big_file)) is False


def test_vision_accepts_valid_jpeg(tmp_path):
    img = tmp_path / "photo.jpg"
    img.write_bytes(b"\xff\xd8\xff")  # JPEG magic bytes
    analyzer = VisionAnalyzer()
    assert analyzer.validate_image(str(img)) is True


def test_vision_result_structure(mock_vision):
    result = mock_vision.analyze("dummy.jpg", "What is wrong?")
    assert len(result.observations) > 0
    assert len(result.candidates) > 0
    assert 0.0 <= result.confidence <= 1.0
    assert result.uncertainty != ""
    assert result.limitations != ""


def test_vision_analyzer_disabled():
    analyzer = VisionAnalyzer(enabled=False)
    result = analyzer.analyze("anything.jpg")
    assert result.uncertainty != ""


# ─── M15: Vision Result Parsing ─────────────────────────────────────────────

def test_vision_result_represents_uncertainty():
    result = VisionResult(
        observations=["Leaf spot visible"],
        candidates=["Bacterial leaf spot", "Fungal infection"],
        confidence=0.6,
        uncertainty="Cannot confirm pathogen from image alone",
        limitations="Requires lab testing for definitive diagnosis",
    )
    assert result.confidence < 1.0
    assert "cannot confirm" in result.uncertainty.lower()
    assert len(result.candidates) > 1  # Differential, not definitive


# ─── M14/M15: Regression - Backward Compatibility ───────────────────────────

def test_farmer_context_merge():
    ctx1 = FarmerContext(crop="Wheat", country="Pakistan")
    ctx2 = FarmerContext(crop="Rice", country="India", province="Punjab")
    merged = ctx1.merge(ctx2)
    assert merged.crop == "Rice"
    assert merged.country == "India"
    assert merged.province == "Punjab"


def test_farmer_context_validation():
    ctx = FarmerContext(crop="", country="")
    errors = ctx.validate()
    assert len(errors) > 0


def test_farmer_context_serialization():
    ctx = FarmerContext(crop="Maize", country="Pakistan")
    js = ctx.to_json()
    new_ctx = FarmerContext.from_json(js)
    assert new_ctx.crop == "Maize"
    assert new_ctx.country == "Pakistan"
