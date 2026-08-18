"""Conversational Context Manager for the Agricultural AI Agent.

Uses MemoryRepository for persistence. No competing storage layers.
"""
from __future__ import annotations

import uuid
from typing import Optional

from app.farmer_context import FarmerContext

_VALID_CTX_KEYS = set(FarmerContext.__dataclass_fields__)


class ContextManager:
    """Manages farmer context and session state across multi-turn conversations.

    Uses an in-memory cache backed by MemoryRepository for persistence.
    """

    def __init__(self, memory=None):
        self._sessions: dict[str, FarmerContext] = {}
        self._memory = memory

    def get_or_create_context(
        self,
        session_id: Optional[str] = None,
        context_data: Optional[dict] = None,
    ) -> FarmerContext:
        """Retrieve existing context (from cache/memory/storage) or create a new one."""
        if not session_id:
            session_id = str(uuid.uuid4())

        ctx = self._sessions.get(session_id)

        if ctx is None and self._memory:
            data = self._memory.get_context(session_id)
            if data:
                defaults = {"crop": "Wheat", "country": "Pakistan"}
                defaults.update({k: v for k, v in data.items() if k in _VALID_CTX_KEYS})
                ctx = FarmerContext(**defaults)

        if ctx is None:
            defaults = {"crop": "Wheat", "country": "Pakistan"}
            if context_data:
                for k, v in context_data.items():
                    if k in _VALID_CTX_KEYS and v is not None:
                        defaults[k] = v
            ctx = FarmerContext(**defaults)

        if context_data:
            updates = {k: v for k, v in context_data.items() if k in _VALID_CTX_KEYS and v is not None}
            if updates:
                if "crop" not in updates and ctx.crop:
                    updates["crop"] = ctx.crop
                if "country" not in updates and ctx.country:
                    updates["country"] = ctx.country
                ctx = ctx.merge(FarmerContext(**updates))

        self._sessions[session_id] = ctx
        if self._memory:
            self._memory.save_context(session_id, ctx.__dict__)

        return ctx

    def get_context(self, session_id: str) -> Optional[FarmerContext]:
        """Get context for a session without creating a new one."""
        if session_id in self._sessions:
            return self._sessions[session_id]
        if self._memory:
            data = self._memory.get_context(session_id)
            if data:
                defaults = {"crop": "Wheat", "country": "Pakistan"}
                stored_data = {k: v for k, v in data.items() if k in _VALID_CTX_KEYS}
                merged_data = {**defaults, **stored_data}
                ctx = FarmerContext(**merged_data)
                self._sessions[session_id] = ctx
                return ctx
        return None

    def update_context(self, session_id: str, context_data: dict) -> Optional[FarmerContext]:
        """Explicitly update a session's context."""
        ctx = self.get_context(session_id)
        if not ctx:
            return None
        updates = {k: v for k, v in context_data.items() if k in _VALID_CTX_KEYS and v is not None}
        new_ctx = ctx.merge(FarmerContext(**updates))
        self._sessions[session_id] = new_ctx
        if self._memory:
            self._memory.save_context(session_id, new_ctx.__dict__)
        return new_ctx

    def clear_session(self, session_id: str) -> bool:
        """Clear a session from the in-memory cache."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False
