"""
Milestone 12 tests: Embedding-based / Hybrid Retrieval.

Tests verify:
- embedding generation (mocked)
- vector index rebuilding
- semantic search
- hybrid ranking
- fallback behavior
"""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from app.knowledge import LocalKnowledgeRetriever, load_knowledge_documents
from app.vector_index import VectorIndex, VECTOR_INDEX_FILE

@pytest.fixture
def mock_embedding():
    """Mock get_embedding to return deterministic values based on text."""
    def _mock_get_embedding(text):
        # Return a simple vector based on word presence
        vec = [0.0] * 10
        if "wheat" in text.lower():
            vec[0] = 1.0
        if "rice" in text.lower():
            vec[1] = 1.0
        if "sowing" in text.lower():
            vec[2] = 1.0
        if "irrigation" in text.lower():
            vec[3] = 1.0
        return vec
    
    with patch("app.vector_index.get_embedding", side_effect=_mock_get_embedding):
        yield

def test_vector_index_rebuild(mock_embedding, tmp_path, monkeypatch):
    index_dir = tmp_path / "index"
    index_file = index_dir / "vector_index.json"
    monkeypatch.setattr("app.vector_index.INDEX_DIR", index_dir)
    monkeypatch.setattr("app.vector_index.VECTOR_INDEX_FILE", index_file)

    vi = VectorIndex()
    vi.rebuild()

    assert index_file.exists()
    data = json.loads(index_file.read_text(encoding="utf-8"))
    assert "index" in data
    assert len(data["index"]) > 0

def test_semantic_search(mock_embedding, tmp_path, monkeypatch):
    index_dir = tmp_path / "index"
    index_file = index_dir / "vector_index.json"
    monkeypatch.setattr("app.vector_index.INDEX_DIR", index_dir)
    monkeypatch.setattr("app.vector_index.VECTOR_INDEX_FILE", index_file)

    vi = VectorIndex()
    vi.rebuild()
    
    # Query for wheat
    results = vi.search("wheat sowing")
    assert len(results) > 0
    # Should find wheat documents with high similarity
    assert any("wheat" in path.lower() for path, sim in results)

def test_hybrid_retrieval_boosts_relevant_results(mock_embedding, tmp_path, monkeypatch):
    # Setup temporary knowledge and index
    index_dir = tmp_path / "index"
    index_file = index_dir / "vector_index.json"
    monkeypatch.setattr("app.vector_index.INDEX_DIR", index_dir)
    monkeypatch.setattr("app.vector_index.VECTOR_INDEX_FILE", index_file)
    
    vi = VectorIndex()
    vi.rebuild()
    
    # With hybrid retrieval, wheat query should strongly favor wheat docs
    retriever = LocalKnowledgeRetriever()
    results = retriever.retrieve("wheat")
    
    assert results
    assert "wheat" in results[0].source.lower()

def test_fallback_when_embeddings_fail(tmp_path, monkeypatch):
    index_dir = tmp_path / "index"
    index_file = index_dir / "vector_index.json"
    monkeypatch.setattr("app.vector_index.INDEX_DIR", index_dir)
    monkeypatch.setattr("app.vector_index.VECTOR_INDEX_FILE", index_file)

    # Force embedding failure
    with patch("app.vector_index.get_embedding", return_value=None):
        retriever = LocalKnowledgeRetriever()
        results = retriever.retrieve("wheat")
        # System should still return results via heuristic
        assert results
        assert "wheat" in results[0].source.lower()

def test_empty_index_behavior(tmp_path, monkeypatch):
    index_dir = tmp_path / "index"
    index_file = index_dir / "vector_index.json"
    monkeypatch.setattr("app.vector_index.INDEX_DIR", index_dir)
    monkeypatch.setattr("app.vector_index.VECTOR_INDEX_FILE", index_file)

    vi = VectorIndex()
    # No rebuild, index is empty
    results = vi.search("wheat")
    assert results == []
