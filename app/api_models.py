"""M16 Production API — Pydantic request/response models."""
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=5000, description="Farmer query text")
    farmer_id: Optional[str] = Field(None, max_length=128)
    session_id: Optional[str] = Field(None, max_length=128)
    context_data: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = Field(None, max_length=128, description="Client-supplied request ID")


class QueryResponse(BaseModel):
    request_id: str
    status: str = "success"
    is_clarification_required: bool
    response: Optional[Dict[str, Any]] = None
    clarification: Optional[Dict[str, Any]] = None
    farmer_text: Optional[str] = None
    intent: Optional[str] = None
    risk_level: Optional[str] = None
    safety_validated: Optional[bool] = None
    evidence_sources: list[str] = []
    warnings: list[str] = []
    latency_ms: float = 0.0


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    database: str = "ok"
    environment: str = "development"


class ErrorResponse(BaseModel):
    request_id: str
    status: str = "error"
    error: str
    detail: Optional[str] = None
