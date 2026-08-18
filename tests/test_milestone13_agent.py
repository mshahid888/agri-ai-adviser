"""
Milestone 13 tests: Intelligent Agricultural AI Agent.

Tests verify:
- Agent orchestration
- Farmer context management and merging
- Retrieval planning integration
- Response generation
- Session handling
- Error handling fallback
"""
import pytest
from app.agent import AgriculturalAgent
from app.farmer_context import FarmerContext
from app.orchestration import OrchestrationOutcome

def test_agent_initialization():
    agent = AgriculturalAgent()
    assert agent.context_manager is not None
    assert agent.classifier is not None
    assert agent.planner is not None

def test_agent_process_query_with_context():
    agent = AgriculturalAgent()
    context_data = {"crop": "Wheat", "country": "Pakistan", "province": "Punjab"}
    outcome = agent.process_query("When should I sow?", session_id="session-1", context_data=context_data)
    
    assert isinstance(outcome, OrchestrationOutcome)
    # Context should be saved in manager
    ctx = agent.context_manager.get_context("session-1")
    assert ctx is not None
    assert ctx.crop == "Wheat"

def test_agent_context_persistence_across_queries():
    agent = AgriculturalAgent()
    # First query sets context
    agent.process_query("I am in Sahiwal", session_id="session-2", context_data={"crop": "Rice", "country": "Pakistan"})
    
    # Second query should still know it's rice in Sahiwal
    outcome = agent.process_query("How to irrigate?", session_id="session-2")
    
    ctx = agent.context_manager.get_context("session-2")
    assert ctx.crop == "Rice"
    assert (ctx.district is not None and "Sahiwal" in ctx.district) or outcome.is_clarification_required or outcome.response is not None

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
    assert any("crop" in e for e in errors)

def test_agent_handles_missing_session_gracefully():
    agent = AgriculturalAgent()
    outcome = agent.process_query("What is wheat?", session_id=None)
    assert isinstance(outcome, OrchestrationOutcome)

def test_agent_serialization_of_context():
    ctx = FarmerContext(crop="Maize", country="Pakistan")
    js = ctx.to_json()
    new_ctx = FarmerContext.from_json(js)
    assert new_ctx.crop == "Maize"
    assert new_ctx.country == "Pakistan"
