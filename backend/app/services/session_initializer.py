"""Orchestrates scenario loading, validation, and initial GameState creation."""

from __future__ import annotations

from pathlib import Path

from backend.app.core.session_store import SessionStore
from backend.app.core.validators import validate_scenario_package
from backend.app.domain.game_state import (
    CastState,
    ConversationState,
    FlagsState,
    GameState,
    HeirState,
    StewardState,
)
from backend.app.services.scenario_loader import ScenarioLoader


class SessionInitializer:
    """Creates a fully initialized session from a scenario ID."""

    def __init__(self, loader: ScenarioLoader, store: SessionStore) -> None:
        self._loader = loader
        self._store = store

    def initialize_session(self, scenario_id: str) -> str:
        """Load scenario, validate, build initial GameState, store session. Returns session ID."""
        package = self._loader.load_scenario_package(scenario_id)

        errors = validate_scenario_package(package)
        if errors:
            raise ValueError(f"Scenario validation failed: {errors}")

        init = package.initial_state
        game_state = GameState(
            location=init.starting_location,
            addressed_character=init.starting_addressed_character,
            flags=FlagsState(
                archive_unlocked=init.initial_flags.archive_unlocked,
                game_finished=init.initial_flags.game_finished,
            ),
            story_truth=package.story.story_truth,
            conversation_state=ConversationState(
                last_speaker=init.initial_conversation_state.last_speaker,
                steward_pressure=init.initial_conversation_state.steward_pressure,
                discovered_topics=list(init.initial_conversation_state.discovered_topics),
                summary=init.initial_conversation_state.summary,
            ),
            cast_state=CastState(
                steward=StewardState(
                    available=init.initial_cast_state.steward.available,
                    yielded=init.initial_cast_state.steward.yielded,
                ),
                heir=HeirState(
                    available=init.initial_cast_state.heir.available,
                ),
            ),
        )

        return self._store.create_session(game_state, package)
