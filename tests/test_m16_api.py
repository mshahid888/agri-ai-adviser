"""M16 Production API Tests — comprehensive coverage."""
import os
import json
import time
import tempfile
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

# Ensure we don't need real API keys for tests
os.environ.setdefault("API_KEY", "test-key-123")
os.environ.setdefault("CORS_ORIGINS", "*")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "100")
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("AGENT_DB_PATH", ":memory:")

from app.api import app, get_agent, _rate_limiter, RateLimiter
from app.agent import AgriculturalAgent
from app.memory import MemoryRepository
from app.config import API_KEY as CONFIGURED_API_KEY


@pytest.fixture
def client():
    """Create a test client with isolated database."""
    from app import api as api_module
    
    # Reset agent and rate limiter for each test
    test_db = tempfile.mktemp(suffix=".db")
    test_agent = AgriculturalAgent(db_path=test_db)
    api_module._agent = test_agent
    api_module._rate_limiter = RateLimiter()
    
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    
    test_agent.memory.close()
    if os.path.exists(test_db):
        os.unlink(test_db)


@pytest.fixture
def auth_headers():
    return {"X-API-Key": "test-key-123"}


@pytest.fixture
def mock_agent(monkeypatch):
    """Create a mock agent for tests that don't need real processing."""
    from app.orchestration import OrchestrationOutcome, ClarificationResult
    from app.adviser import AgriculturalResponse, AgriculturalIntent, RiskLevel
    
    mock = MagicMock(spec=AgriculturalAgent)
    
    mock_response = AgriculturalResponse(
        situation="Wheat sowing query",
        assessment="General guidance based on local knowledge",
        recommendations=["Prepare seedbed", "Check soil moisture"],
        reasons="Based on retrieved agricultural evidence",
        missing_information=[],
        warnings=["Consult local expert for specific rates"],
        confidence="Moderate",
        evidence_sources=["wheat.md"],
        next_questions=["What is your soil type?"],
        intent=AgriculturalIntent.SOWING_PREPARATION,
        risk_level=RiskLevel.LOW,
        safety_validated=True,
    )
    
    mock.process_query.return_value = OrchestrationOutcome(
        is_clarification_required=False,
        response=mock_response,
    )
    return mock


@pytest.fixture
def mock_clarification_agent():
    """Create a mock agent that returns clarification."""
    from app.orchestration import OrchestrationOutcome, ClarificationResult
    
    mock = MagicMock(spec=AgriculturalAgent)
    mock.process_query.return_value = OrchestrationOutcome(
        is_clarification_required=True,
        clarification=ClarificationResult(
            missing_information=["soil_type"],
            why_it_matters="Soil type is needed for fertilizer recommendations",
            follow_up_questions=["What is your soil type?"],
            safe_general_guidance=["General guidance can still be provided"],
            reason="Soil information required",
        ),
    )
    return mock


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "environment" in data

    def test_health_includes_database_status(self, client):
        response = client.get("/api/v1/health")
        data = response.json()
        assert "database" in data
        assert data["database"] in ("ok", "error")

    def test_health_no_auth_required(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code == 200


class TestQueryEndpoint:
    def test_query_success(self, client, mock_agent, auth_headers):
        from app import api as api_module
        api_module._agent = mock_agent
        
        response = client.post(
            "/api/v1/query",
            data={"question": "When to sow wheat?"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["request_id"]
        assert data["is_clarification_required"] is False
        assert data["intent"] == "sowing_preparation"

    def test_query_with_farmer_id(self, client, mock_agent, auth_headers):
        from app import api as api_module
        api_module._agent = mock_agent
        
        response = client.post(
            "/api/v1/query",
            data={"question": "When to sow wheat?", "farmer_id": "farmer-123"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    def test_query_with_session_id(self, client, mock_agent, auth_headers):
        from app import api as api_module
        api_module._agent = mock_agent
        
        response = client.post(
            "/api/v1/query",
            data={"question": "When to sow wheat?", "session_id": "sess-456"},
            headers=auth_headers,
        )
        assert response.status_code == 200

    def test_query_missing_question(self, client, auth_headers):
        response = client.post(
            "/api/v1/query",
            data={},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_query_empty_question(self, client, auth_headers):
        response = client.post(
            "/api/v1/query",
            data={"question": ""},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_query_get_not_allowed(self, client, auth_headers):
        response = client.get("/api/v1/query", headers=auth_headers)
        assert response.status_code == 405

    def test_query_clarification_flow(self, client, mock_clarification_agent, auth_headers):
        from app import api as api_module
        api_module._agent = mock_clarification_agent
        
        response = client.post(
            "/api/v1/query",
            data={"question": "What fertilizer should I use?"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_clarification_required"] is True
        assert data["clarification"] is not None
        assert "follow_up_questions" in data["clarification"]

    def test_query_returns_latency(self, client, mock_agent, auth_headers):
        from app import api as api_module
        api_module._agent = mock_agent
        
        response = client.post(
            "/api/v1/query",
            data={"question": "When to sow wheat?"},
            headers=auth_headers,
        )
        data = response.json()
        assert "latency_ms" in data
        assert data["latency_ms"] >= 0


class TestAuthentication:
    def test_missing_api_key_rejected(self, client):
        response = client.post(
            "/api/v1/query",
            data={"question": "When to sow wheat?"},
        )
        assert response.status_code == 401

    def test_invalid_api_key_rejected(self, client):
        response = client.post(
            "/api/v1/query",
            data={"question": "When to sow wheat?"},
            headers={"X-API-Key": "wrong-key"},
        )
        assert response.status_code == 401

    def test_valid_api_key_accepted(self, client, mock_agent, auth_headers):
        from app import api as api_module
        api_module._agent = mock_agent
        
        response = client.post(
            "/api/v1/query",
            data={"question": "When to sow wheat?"},
            headers=auth_headers,
        )
        assert response.status_code == 200


class TestRateLimiting:
    def test_rate_limiter_allows_within_limit(self):
        limiter = RateLimiter()
        for i in range(5):
            assert limiter.check("test-key", limit=10, window=60) is True

    def test_rate_limiter_blocks_over_limit(self):
        limiter = RateLimiter()
        for i in range(10):
            limiter.check("test-key", limit=10, window=60)
        assert limiter.check("test-key", limit=10, window=60) is False

    def test_rate_limiter_separate_keys(self):
        limiter = RateLimiter()
        for i in range(10):
            limiter.check("key-1", limit=10, window=60)
        assert limiter.check("key-2", limit=10, window=60) is True


class TestImageUpload:
    def test_query_with_valid_image(self, client, mock_agent, auth_headers):
        from app import api as api_module
        api_module._agent = mock_agent
        
        # Create a minimal JPEG-like file
        img_data = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(img_data)
            temp_path = f.name
        
        try:
            with open(temp_path, "rb") as img_file:
                response = client.post(
                    "/api/v1/query",
                    data={"question": "What is wrong with my crop?"},
                    files={"image": ("test.jpg", img_file, "image/jpeg")},
                    headers=auth_headers,
                )
            assert response.status_code == 200
        finally:
            os.unlink(temp_path)

    def test_query_with_invalid_image_format(self, client, auth_headers):
        # Try uploading a .txt file with image field name
        txt_data = b"not an image"
        response = client.post(
            "/api/v1/query",
            data={"question": "What is wrong?"},
            files={"image": ("notes.txt", txt_data, "text/plain")},
            headers=auth_headers,
        )
        # Should reject invalid format
        assert response.status_code == 400


class TestRequestId:
    def test_request_id_generated(self, client, mock_agent, auth_headers):
        from app import api as api_module
        api_module._agent = mock_agent
        
        response = client.post(
            "/api/v1/query",
            data={"question": "When to sow wheat?"},
            headers=auth_headers,
        )
        assert "x-request-id" in response.headers
        assert response.headers["x-request-id"]

    def test_request_id_propagated(self, client, mock_agent, auth_headers):
        from app import api as api_module
        api_module._agent = mock_agent
        
        custom_id = "my-custom-request-id"
        response = client.post(
            "/api/v1/query",
            data={"question": "When to sow wheat?"},
            headers={**auth_headers, "X-Request-ID": custom_id},
        )
        assert response.headers["x-request-id"] == custom_id
        data = response.json()
        assert data["request_id"] == custom_id


class TestFeedbackEndpoint:
    def test_submit_feedback(self, client, auth_headers):
        from app import api as api_module
        api_module._agent.memory.save_feedback("test-interaction", 5, "Great advice")
        
        response = client.post(
            "/api/v1/feedback",
            data={"interaction_id": "test-interaction", "rating": 4, "comment": "Good"},
            headers=auth_headers,
        )
        assert response.status_code == 200

    def test_feedback_invalid_rating(self, client, auth_headers):
        response = client.post(
            "/api/v1/feedback",
            data={"interaction_id": "i1", "rating": 6, "comment": "Too high"},
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestCORSMiddleware:
    def test_cors_headers(self, client):
        response = client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        # CORS middleware should handle this
        assert response.status_code in (200, 405)


class TestErrorHandling:
    def test_agent_exception_returns_500(self, client, auth_headers):
        from app import api as api_module
        mock = MagicMock(spec=AgriculturalAgent)
        mock.process_query.side_effect = RuntimeError("LLM connection failed")
        api_module._agent = mock
        
        response = client.post(
            "/api/v1/query",
            data={"question": "When to sow?"},
            headers=auth_headers,
        )
        assert response.status_code == 500
        data = response.json()
        assert "error" in data["detail"].lower() or "internal" in data["detail"].lower()


class TestLoggingBehavior:
    def test_request_logged(self, client, mock_agent, auth_headers, caplog):
        from app import api as api_module
        api_module._agent = mock_agent
        
        with caplog.at_level("INFO", logger="agriai.api"):
            client.post(
                "/api/v1/query",
                data={"question": "When to sow wheat?"},
                headers=auth_headers,
            )
        
        log_records = [r for r in caplog.records if r.name == "agriai.api"]
        assert len(log_records) > 0

    def test_no_secrets_in_logs(self, client, mock_agent, auth_headers, caplog):
        from app import api as api_module
        api_module._agent = mock_agent
        
        with caplog.at_level("INFO", logger="agriai.api"):
            client.post(
                "/api/v1/query",
                data={"question": "When to sow wheat?"},
                headers=auth_headers,
            )
        
        for record in caplog.records:
            assert "test-key-123" not in record.message
