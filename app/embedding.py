"""Embedding generation and semantic similarity for the Agri-AI Adviser.

Provides optional embedding-based retrieval capabilities.
"""
from __future__ import annotations

import math
from typing import Optional

from openai import OpenAI
from app.config import EMBEDDING_MODEL, OMNIROUTE_BASE_URL, OMNIROUTE_API_KEY

def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(vec1) != len(vec2) or not vec1 or not vec2:
        return 0.0
    
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    return dot_product / (norm1 * norm2)

def get_embedding(text: str) -> Optional[list[float]]:
    """Generate embedding for the given text using OpenAI API."""
    if not OMNIROUTE_API_KEY:
        return None
        
    try:
        client = OpenAI(
            base_url=OMNIROUTE_BASE_URL,
            api_key=OMNIROUTE_API_KEY,
        )
        response = client.embeddings.create(
            input=text,
            model=EMBEDDING_MODEL
        )
        return response.data[0].embedding
    except Exception:
        # Fallback gracefully if embedding service fails
        return None
