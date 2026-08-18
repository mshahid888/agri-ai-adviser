# AI Agricultural Adviser — Punjab, Pakistan

An AI-powered agricultural decision-support system for farmers in Punjab, Pakistan.

## Quick Start

### 1. Install dependencies

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 2. Configure environment

Copy `.env.example` to `.env` and fill in:

```bash
cp .env.example .env
```

Required:
- `OMNIROUTE_API_KEY` — LLM API key

Optional:
- `API_KEY` — HTTP API authentication key (disabled if unset)

### 3. Start the API

```bash
uvicorn app.api:app --reload
```

API available at `http://localhost:8000`

### 4. Run tests

```bash
pytest tests/ -v
```

## API Usage

### Health check
```bash
curl http://localhost:8000/api/v1/health
```

### Query (text only)
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "X-API-Key: your_api_key" \
  -F "question=When should I sow wheat in Sahiwal?"
```

### Query (with image)
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "X-API-Key: your_api_key" \
  -F "question=What is wrong with my crop?" \
  -F "image=@crop_photo.jpg"
```

### Feedback
```bash
curl -X POST http://localhost:8000/api/v1/feedback \
  -H "X-API-Key: your_api_key" \
  -F "interaction_id=i1" \
  -F "rating=5" \
  -F "comment=Great advice"
```

## Docker

```bash
docker-compose up -d
```

## Architecture

```
FastAPI API → Auth → Rate Limit → AgriculturalAgent → Knowledge RAG → LLM → Validated Response
```

Core components:
- **Retrieval:** Hybrid keyword + semantic search over local agricultural knowledge
- **Agent:** Intent classification → retrieval planning → evidence validation → LLM reasoning
- **Memory:** Persistent farmer profiles, sessions, interactions, feedback (SQLite)
- **Vision:** Multimodal image analysis for crop diagnosis
- **Safety:** Deterministic guardrails preventing unsupported specific recommendations

## Milestones

| Milestone | Scope | Status |
|-----------|-------|--------|
| M3–M8 | Knowledge retrieval, validation, safety, response engine | Complete |
| M9–M11 | Official KB, PDF ingestion, production schema | Complete |
| M12 | Semantic retrieval, embeddings, intent classification | Complete |
| M13 | Intelligent agent pipeline | Complete |
| M14 | Persistent memory (SQLite) | Complete |
| M15 | Multimodal vision analysis | Complete |
| M16 | Production API service & observability | Complete |

See `MILESTONE_*_IMPLEMENTATION.md` files for detailed documentation.

## Project Structure

```
app/
  api.py              M16: FastAPI HTTP service
  api_models.py       M16: Pydantic request/response models
  agent.py            M13: Agent orchestration
  memory.py           M14: Persistent memory (SQLite)
  vision.py           M15: Multimodal image analysis
  config.py           Configuration (env vars)
  orchestrator.py     Query pipeline
  knowledge.py        Hybrid knowledge retrieval
  embedding.py        Semantic search
  adviser.py          LLM interaction + safety
  safety_layer.py     Deterministic safety checks
  ...
tests/                330 tests across 19 test files
knowledge/            Agricultural knowledge base
data/                 SQLite database
```

## License

Internal project — not licensed for distribution.
