# Milestone 16 Implementation: Production API Service & Observability

## Overview

Milestone 16 transforms the in-process agricultural AI agent into a production-deployable HTTP service. The existing M1–M15 agent pipeline is preserved exactly — M16 adds a FastAPI layer on top without modifying any core agent logic.

## Architecture

```
Client
  ↓
FastAPI API (app/api.py)
  ↓
Authentication (API key via X-API-Key header)
  ↓
Rate Limiting (sliding window per client)
  ↓
Request ID (X-Request-ID, generated if absent)
  ↓
Structured Logging (request_id, endpoint, latency, status)
  ↓
AgriculturalAgent (app/agent.py — unchanged M13/M14/M15)
  ↓
Farmer Profile / Persistent Memory (M14)
  ↓
Session / Context Management (M14)
  ↓
Intent Classification (M12.5)
  ↓
Retrieval Planning (M13)
  ↓
Hybrid Knowledge Retrieval (M12.6)
  ↓
Vision when image supplied (M15)
  ↓
Safety Layer (M6+)
  ↓
Orchestration / LLM (M6)
  ↓
Response Validation (M4)
  ↓
Memory / Interaction Persistence (M14)
  ↓
API Response (JSON)
```

## API Endpoints

### POST `/api/v1/query`
Main query endpoint. Accepts multipart form data.

**Request:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| question | string | Yes | Farmer query (1–5000 chars) |
| farmer_id | string | No | Farmer identifier |
| session_id | string | No | Session identifier for multi-turn |
| image | file | No | Image upload (jpg/png/webp, ≤10MB) |

**Headers:**
| Header | Required | Description |
|--------|----------|-------------|
| X-API-Key | Yes* | API authentication key |
| X-Request-ID | No | Client-supplied request ID |

**Response (200):**
```json
{
  "request_id": "uuid",
  "status": "success",
  "is_clarification_required": false,
  "response": {
    "situation": "...",
    "assessment": "...",
    "recommendations": ["..."],
    "reasons": "...",
    "warnings": ["..."],
    "confidence": "Moderate",
    "next_questions": ["..."]
  },
  "farmer_text": "...",
  "intent": "sowing_preparation",
  "risk_level": "low",
  "safety_validated": true,
  "evidence_sources": ["..."],
  "latency_ms": 1234.56
}
```

**Error Responses:**
- `401` — Missing or invalid API key
- `405` — GET not allowed on query endpoint
- `413` — Image too large
- `400` — Unsupported image format
- `422` — Validation error (missing/invalid fields)
- `429` — Rate limit exceeded
- `500` — Internal server error

### GET `/api/v1/health`
Health check. No authentication required.

**Response (200):**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "database": "ok",
  "environment": "development"
}
```

Returns `503` if database is unreachable.

### POST `/api/v1/feedback`
Submit farmer feedback. Requires authentication.

**Request (form data):**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| interaction_id | string | Yes | Interaction identifier |
| rating | int | Yes | 1–5 rating |
| comment | string | No | Free-text comment |

## Authentication

API-key authentication via `X-API-Key` header.

- Configure `API_KEY` in `.env` or environment
- When `API_KEY` is not set, authentication is disabled (dev mode)
- Missing/invalid key returns HTTP 401
- Key is never logged or exposed in responses

## Rate Limiting

Sliding-window rate limiting per API key.

- Default: 10 requests/minute per client
- Configure via `RATE_LIMIT_PER_MINUTE`
- Returns HTTP 429 when exceeded
- Separate tracking per unique API key

## Request ID

Every request receives a unique `X-Request-ID`:

1. Client sends `X-Request-ID` → used as-is
2. Client omits it → server generates UUID
3. Returned in response header and JSON body
4. Included in all log entries for the request

## Structured Logging

All API requests log:
- `request_id` — unique identifier
- `endpoint` — URL path
- `method` — HTTP method
- `status_code` — response status
- `duration_ms` — request latency

**Never logged:**
- API keys
- Authentication headers
- Farmer PII beyond farmer_id
- Image contents
- Secrets

## Configuration

All settings via environment variables (`.env` supported):

| Variable | Default | Description |
|----------|---------|-------------|
| `API_HOST` | `0.0.0.0` | Listen address |
| `API_PORT` | `8000` | Listen port |
| `API_KEY` | (none) | Auth key (disabled if unset) |
| `CORS_ORIGINS` | `*` | Allowed origins (comma-separated) |
| `RATE_LIMIT_PER_MINUTE` | `10` | Per-client rate limit |
| `UPLOAD_MAX_SIZE` | `10485760` | Max image upload (bytes) |
| `LOG_LEVEL` | `INFO` | Log verbosity |
| `ENVIRONMENT` | `development` | Environment name |
| `REQUEST_TIMEOUT` | `120` | Request timeout (seconds) |
| `MAX_RETRIES` | `3` | LLM retry count |
| `RETRY_BACKOFF_FACTOR` | `2.0` | Retry backoff multiplier |

Existing M1–M15 configuration remains unchanged.

## Docker Deployment

### Build and run:
```bash
docker-compose up -d
```

### Manual build:
```bash
docker build -t agri-ai-api .
docker run -p 8000:8000 --env-file .env agri-ai-api
```

### Container features:
- Non-root user (`appuser`)
- Health check built in
- Data volume mounted for persistence
- Environment-based configuration
- No secrets in image

## Health Checks

- **Liveness:** `GET /api/v1/health` → 200 if app is running
- **Readiness:** `GET /api/v1/health` → 200 if database is accessible, 503 otherwise
- **Provider status:** External LLM/embedding status is separate; health endpoint does not block on provider availability

## Security Considerations

- API keys never logged or exposed in responses
- Image uploads validated: format, size, existence
- Temporary upload files cleaned up after processing
- Rate limiting prevents abuse
- CORS configurable per environment
- Non-root Docker user
- No hardcoded secrets
- SQL injection prevented by parameterized queries (SQLite)

## SQLite Production Limitations

- Single-writer concurrency (WAL mode enabled)
- No connection pooling
- File-based (backup via file copy)
- Suitable for single-instance deployment
- For multi-instance or high-concurrency: migrate to PostgreSQL

## Testing

```bash
# Run M16 tests only
pytest tests/test_m16_api.py -v

# Run full suite
pytest tests/ -v
```

27 M16-specific tests covering:
- Health endpoint
- Query endpoint (success, clarification, image upload)
- Authentication (missing, invalid, valid)
- Rate limiting
- Request ID generation and propagation
- Feedback endpoint
- Error handling (agent exceptions)
- CORS behavior
- Logging behavior (no secrets in logs)

## Files

### Created
- `app/api.py` — FastAPI application, routes, middleware
- `app/api_models.py` — Pydantic request/response models
- `tests/test_m16_api.py` — 27 API tests
- `Dockerfile` — Container image definition
- `docker-compose.yml` — Multi-service orchestration
- `MILESTONE_16_IMPLEMENTATION.md` — This document

### Modified
- `app/config.py` — Added API configuration variables
- `requirements.txt` — Added FastAPI, uvicorn, python-multipart, httpx
- `.env.example` — Added API configuration examples

### Unmodified
- All M1–M15 source files (`agent.py`, `memory.py`, `vision.py`, `orchestration.py`, etc.)
- All M1–M15 test files

## Future Work (M17+)

- PostgreSQL migration for multi-instance deployment
- Prometheus metrics endpoint
- Structured JSON logging to external aggregator
- WebSocket support for streaming responses
- LLM response caching for repeated queries
- Model provider fallback chain
- Async task queue for long-running queries
- OpenTelemetry distributed tracing
- Grafana dashboard templates
