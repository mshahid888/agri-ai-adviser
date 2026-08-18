"""Vector indexing and semantic search for the Agri-AI Adviser.

Provides a deterministic, reproducible vector index over knowledge documents
to support hybrid semantic-keyword retrieval.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from app.embedding import get_embedding, _cosine_similarity
from app.knowledge import KnowledgeDocument, load_knowledge_documents

logger = logging.getLogger(__name__)

INDEX_DIR = Path(__file__).resolve().parent.parent / "knowledge" / "index"
VECTOR_INDEX_FILE = INDEX_DIR / "vector_index.json"

class VectorIndex:
    """A simple file-based vector index for knowledge documents."""

    def __init__(self):
        self.index: dict[str, list[float]] = {}
        self.document_paths: dict[str, str] = {}
        self._load_index()

    def _load_index(self) -> None:
        if VECTOR_INDEX_FILE.exists():
            try:
                data = json.loads(VECTOR_INDEX_FILE.read_text(encoding="utf-8"))
                self.index = data.get("index", {})
                self.document_paths = data.get("document_paths", {})
            except (json.JSONDecodeError, OSError) as e:
                logger.error(f"Failed to load vector index: {e}")

    def rebuild(self) -> None:
        """Rebuild index from current knowledge base."""
        documents = load_knowledge_documents()
        self.index = {}
        self.document_paths = {}
        
        for doc in documents:
            embedding = get_embedding(doc.content)
            if embedding:
                self.index[doc.path] = embedding
                self.document_paths[doc.path] = doc.path

        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        VECTOR_INDEX_FILE.write_text(
            json.dumps({"index": self.index, "document_paths": self.document_paths}),
            encoding="utf-8"
        )

    def search(self, query: str, top_k: int = 5) -> list[tuple[str, float]]:
        """Perform semantic search."""
        query_embedding = get_embedding(query)
        if not query_embedding or not self.index:
            return []

        similarities = []
        for path, embedding in self.index.items():
            sim = _cosine_similarity(query_embedding, embedding)
            similarities.append((path, sim))

        # Sort by similarity descending
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]
