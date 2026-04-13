"""In-memory session store — maps session IDs to session data."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from backend.app.domain.game_state import GameState
from backend.app.domain.scenario_models import ScenarioPackage


class SessionData(BaseModel):
    """All data associated with a single game session."""

    game_state: GameState
    scenario_package: ScenarioPackage
    turn_index: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SessionStore:
    """Dictionary-backed session store. Replace with Redis/DB later if needed."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionData] = {}

    def create_session(self, game_state: GameState, scenario_package: ScenarioPackage) -> str:
        """Store a new session and return its ID."""
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = SessionData(
            game_state=game_state,
            scenario_package=scenario_package,
        )
        return session_id

    def get_session(self, session_id: str) -> SessionData:
        """Return session data, updating last-accessed time. Raises KeyError if not found."""
        if session_id not in self._sessions:
            raise KeyError(f"Session not found: {session_id}")
        session = self._sessions[session_id]
        session.last_accessed_at = datetime.now(timezone.utc)
        return session

    def update_session(self, session_id: str, game_state: GameState) -> None:
        """Replace the game state for an existing session."""
        session = self.get_session(session_id)
        session.game_state = game_state

    def delete_session(self, session_id: str) -> None:
        """Remove a session from the store."""
        self._sessions.pop(session_id, None)

    def cleanup_expired(self, max_age_minutes: int = 60) -> int:
        """Remove sessions older than *max_age_minutes*. Returns count removed."""
        now = datetime.now(timezone.utc)
        expired = [
            sid
            for sid, data in self._sessions.items()
            if (now - data.last_accessed_at).total_seconds() > max_age_minutes * 60
        ]
        for sid in expired:
            del self._sessions[sid]
        return len(expired)
