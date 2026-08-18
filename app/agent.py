"""Agricultural AI Agent implementation.

Orchestrates the query-to-response pipeline for agricultural advice.
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from app.context_manager import ContextManager
from app.intent_classifier import IntelligentIntentClassifier
from app.memory import MemoryRepository, FarmerProfile, FarmerMemory, Interaction
from app.orchestration import OrchestrationOutcome, ask_farmer
from app.retrieval_planner import RetrievalPlanner
from app.vision import VisionAnalyzer

logger = logging.getLogger(__name__)


class AgriculturalAgent:
    """Production-grade agricultural AI agent.

    Integrates M14 persistent memory and M15 multimodal vision.
    """

    def __init__(self, db_path: str = ":memory:"):
        self.memory = MemoryRepository(db_path=db_path)
        self.context_manager = ContextManager(memory=self.memory)
        self.classifier = IntelligentIntentClassifier()
        self.planner = RetrievalPlanner()
        self.vision = VisionAnalyzer()

    def process_query(
        self,
        question: str,
        session_id: Optional[str] = None,
        context_data: Optional[dict] = None,
        image_path: Optional[str] = None,
        farmer_id: Optional[str] = None,
    ) -> OrchestrationOutcome:
        """Process a farmer's query through the full agent pipeline."""
        if not farmer_id:
            farmer_id = (context_data or {}).get("farmer_id", "anonymous")

        # 1. Persistent farmer profile
        profile = self.memory.get_farmer(farmer_id) or FarmerProfile(farmer_id=farmer_id)
        if context_data:
            for k, v in context_data.items():
                if hasattr(profile, k) and v is not None:
                    setattr(profile, k, v)
        self.memory.upsert_farmer(profile)

        # 2. Session management
        session = self.memory.get_session(session_id) if session_id else None
        if not session:
            session_id = session_id or str(uuid.uuid4())
            session = self.memory.get_session(session_id)
            if not session:
                from datetime import datetime
                session = self.memory.upsert_session(
                    __import__("app.memory", fromlist=["Session"]).Session(
                        session_id=session_id, farmer_id=farmer_id
                    )
                ) or self.memory.get_session(session_id)

        # 3. Relevant memory retrieval
        query_keywords = question.lower().split()
        relevant_memories = self.memory.search_memories(farmer_id, query_keywords, limit=5)
        if relevant_memories:
            history_text = "; ".join(m.content for m in relevant_memories)
            question = f"{question} (Farmer history: {history_text})"

        # 4. Multimodal processing (M15)
        if image_path and self.vision.validate_image(image_path):
            vision_result = self.vision.analyze(image_path, question)
            obs_text = "; ".join(vision_result.observations)
            question = f"{question} (Visual observations: {obs_text})"
            self.memory.add_memory(FarmerMemory(
                memory_id=str(uuid.uuid4()),
                farmer_id=farmer_id,
                memory_type="interaction",
                content=f"Image analysis: {obs_text}. Candidates: {', '.join(vision_result.candidates)}",
            ))

        # 5. Context and orchestration
        context = self.context_manager.get_or_create_context(session_id, context_data)
        outcome = ask_farmer(question, context=context)

        # 6. Persist interaction
        resp_text = ""
        if outcome.clarification:
            resp_text = "; ".join(outcome.clarification.follow_up_questions[:3])
        elif outcome.response:
            resp_text = outcome.response.to_farmer_text()

        intent_str = ""
        if outcome.response and outcome.response.intent:
            intent_str = outcome.response.intent.value

        self.memory.add_interaction(Interaction(
            interaction_id=str(uuid.uuid4()),
            farmer_id=farmer_id,
            session_id=session_id or "null",
            query=question,
            response=resp_text[:500],
            intent=intent_str,
        ))

        return outcome
