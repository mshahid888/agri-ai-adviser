"""M16 Production API — FastAPI application with auth, rate limiting, observability."""
from __future__ import annotations

import logging
import os
import tempfile
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, UploadFile, File, Form, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import (
    API_KEY, API_HOST, API_PORT, CORS_ORIGINS,
    RATE_LIMIT_PER_MINUTE, UPLOAD_MAX_SIZE,
    LOG_LEVEL, ENVIRONMENT, configure_logging,
    AGENT_DB_PATH,
)
from app.api_models import QueryRequest, QueryResponse, HealthResponse, ErrorResponse
from app.agent import AgriculturalAgent
from app.memory import MemoryRepository

configure_logging()
logger = logging.getLogger("agriai.api")

_agent: Optional[AgriculturalAgent] = None


def get_agent() -> AgriculturalAgent:
    global _agent
    if _agent is None:
        _agent = AgriculturalAgent(db_path=AGENT_DB_PATH)
    return _agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Agri-AI Adviser API in %s mode", ENVIRONMENT)
    get_agent()
    yield
    logger.info("Shutting down Agri-AI Adviser API")


app = FastAPI(
    title="Agri-AI Adviser API",
    description="Production API for agricultural AI advisory system",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Simple in-memory rate limiter (sliding window per API key)
class RateLimiter:
    def __init__(self):
        self._requests: dict[str, list[float]] = {}

    def check(self, key: str, limit: int, window: float = 60.0) -> bool:
        now = time.time()
        if key not in self._requests:
            self._requests[key] = []
        self._requests[key] = [t for t in self._requests[key] if now - t < window]
        if len(self._requests[key]) >= limit:
            return False
        self._requests[key].append(now)
        return True


_rate_limiter = RateLimiter()


async def verify_api_key(request: Request) -> str:
    key = os.environ.get("API_KEY", API_KEY or "")
    if not key:
        return "anonymous"
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    if api_key != key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key


async def get_request_id(request: Request) -> str:
    return request.headers.get("X-Request-ID") or str(uuid.uuid4())


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    start_time = time.time()
    
    response = await call_next(request)
    
    duration_ms = (time.time() - start_time) * 1000
    logger.info(
        "api_request",
        extra={
            "request_id": request_id,
            "endpoint": request.url.path,
            "method": request.method,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
        },
    )
    
    response.headers["X-Request-ID"] = request_id
    return response


@app.post("/api/v1/query", response_model=QueryResponse)
async def query_agent(
    request: Request,
    question: str = Form(...),
    farmer_id: Optional[str] = Form(None),
    session_id: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    api_key: str = Depends(verify_api_key),
    request_id: str = Depends(get_request_id),
):
    # Rate limiting
    rate_key = api_key or "anonymous"
    if not _rate_limiter.check(rate_key, RATE_LIMIT_PER_MINUTE):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    start_time = time.time()
    temp_path = None
    
    try:
        # Handle image upload
        image_path = None
        if image:
            content = await image.read()
            if len(content) > UPLOAD_MAX_SIZE:
                raise HTTPException(status_code=413, detail="Image too large")
            
            ext = os.path.splitext(image.filename or "upload.jpg")[1].lower()
            if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
                raise HTTPException(status_code=400, detail="Unsupported image format")
            
            fd, temp_path = tempfile.mkstemp(suffix=ext)
            os.close(fd)
            with open(temp_path, "wb") as f:
                f.write(content)
            image_path = temp_path
        
        # Process query
        agent = get_agent()
        outcome = agent.process_query(
            question=question,
            session_id=session_id,
            context_data={"farmer_id": farmer_id} if farmer_id else None,
            image_path=image_path,
            farmer_id=farmer_id,
        )
        
        latency_ms = (time.time() - start_time) * 1000
        
        # Build response
        response_data = {
            "request_id": request_id,
            "status": "success",
            "is_clarification_required": outcome.is_clarification_required,
            "latency_ms": round(latency_ms, 2),
        }
        
        if outcome.is_clarification_required and outcome.clarification:
            response_data["clarification"] = {
                "missing_information": outcome.clarification.missing_information,
                "why_it_matters": outcome.clarification.why_it_matters,
                "follow_up_questions": outcome.clarification.follow_up_questions,
                "safe_general_guidance": outcome.clarification.safe_general_guidance,
            }
            response_data["farmer_text"] = "\n".join(
                outcome.clarification.follow_up_questions
            )
        elif outcome.response:
            response_data["response"] = {
                "situation": outcome.response.situation,
                "assessment": outcome.response.assessment,
                "recommendations": outcome.response.recommendations,
                "reasons": outcome.response.reasons,
                "warnings": outcome.response.warnings,
                "confidence": outcome.response.confidence,
                "next_questions": outcome.response.next_questions,
            }
            response_data["farmer_text"] = outcome.response.to_farmer_text()
            response_data["intent"] = outcome.response.intent.value
            response_data["risk_level"] = outcome.response.risk_level.value
            response_data["safety_validated"] = outcome.response.safety_validated
            response_data["evidence_sources"] = outcome.response.evidence_sources
            response_data["warnings"] = outcome.response.warnings
        
        return QueryResponse(**response_data)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("query_error", extra={"request_id": request_id, "error": str(e)})
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


@app.get("/api/v1/query")
async def query_get_not_allowed():
    raise HTTPException(status_code=405, detail="Use POST for queries")


@app.get("/api/v1/health", response_model=HealthResponse)
async def health_check():
    db_status = "ok"
    try:
        repo = MemoryRepository(db_path=AGENT_DB_PATH)
        repo.conn.execute("SELECT 1")
        repo.close()
    except Exception:
        db_status = "error"
    
    status_code = 200 if db_status == "ok" else 503
    response = HealthResponse(
        status=db_status,
        database=db_status,
        environment=ENVIRONMENT,
    )
    if status_code != 200:
        return JSONResponse(content=response.model_dump(), status_code=status_code)
    return response


@app.post("/api/v1/feedback")
async def submit_feedback(
    interaction_id: str = Form(...),
    rating: int = Form(..., ge=1, le=5),
    comment: Optional[str] = Form(""),
    api_key: str = Depends(verify_api_key),
):
    agent = get_agent()
    try:
        agent.memory.save_feedback(interaction_id, rating, comment)
        return {"status": "success", "message": "Feedback recorded"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.api:app",
        host=API_HOST,
        port=API_PORT,
        reload=ENVIRONMENT == "development",
    )
