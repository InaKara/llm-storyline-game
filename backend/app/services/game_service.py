"""Thin coordinator that orchestrates the full turn pipeline."""

from __future__ import annotations

import re

from backend.app.core.session_store import SessionStore
from backend.app.core.trace_logger import TraceLogger
from backend.app.domain.game_state import GameState, TurnRecord
from backend.app.domain.progress_models import ProgressEvaluatorOutput, StateEffects
from backend.app.domain.response_models import ResponseConstraints, TurnResult
from backend.app.domain.scenario_models import ScenarioPackage
from backend.app.services.character_responder import CharacterResponder
from backend.app.services.constraint_builder import ConstraintBuilder
from backend.app.services.progress_evaluator import ProgressEvaluator
from backend.app.services.prompt_builder import PromptBuilder
from backend.app.services.session_initializer import SessionInitializer
from backend.app.services.state_updater import StateUpdater

# Simple movement patterns — avoids a third LLM call per turn
_MOVEMENT_RE = re.compile(
    r"^(?:go\s+to|move\s+to|enter|walk\s+to|head\s+to)\s+(?:the\s+)?(.+)$",
    re.IGNORECASE,
)


class GameService:
    """Orchestrates session lifecycle and the turn pipeline."""

    def __init__(
        self,
        store: SessionStore,
        initializer: SessionInitializer,
        state_updater: StateUpdater,
        constraint_builder: ConstraintBuilder,
        progress_evaluator: ProgressEvaluator | None = None,
        character_responder: CharacterResponder | None = None,
        prompt_builder: PromptBuilder | None = None,
        trace_logger: TraceLogger | None = None,
        asset_base_url: str = "/assets",
    ) -> None:
        self._store = store
        self._initializer = initializer
        self._state_updater = state_updater
        self._constraint_builder = constraint_builder
        self._evaluator = progress_evaluator
        self._responder = character_responder
        self._prompt_builder = prompt_builder
        self._trace_logger = trace_logger
        self._asset_base_url = asset_base_url.rstrip("/")

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def create_session(self, scenario_id: str) -> tuple[str, TurnResult]:
        """Create a new session and return (session_id, opening_scene)."""
        session_id = self._initializer.initialize_session(scenario_id)
        session = self._store.get_session(session_id)
        turn_result = self._build_narrator_turn(
            session.game_state,
            session.scenario_package,
            self._opening_dialogue(session.scenario_package),
        )
        return session_id, turn_result

    def get_state(self, session_id: str) -> GameState:
        """Return the current game state for a session."""
        return self._store.get_session(session_id).game_state

    def submit_turn(self, session_id: str, player_input: str) -> tuple[int, TurnResult]:
        """Process one player turn. Returns (turn_index, TurnResult).

        Detects movement commands via simple pattern matching. Everything else
        goes through the evaluator → state updater → constraint builder →
        responder pipeline.
        """
        session = self._store.get_session(session_id)
        gs = session.game_state
        pkg = session.scenario_package

        # --- Input classification: movement vs character interaction ---
        move_match = _MOVEMENT_RE.match(player_input.strip())
        if move_match:
            target_raw = move_match.group(1).strip().lower()
            # Match against available exit IDs and location names
            target_id = self._resolve_location(target_raw, gs, pkg)
            if target_id and target_id in gs.available_exits:
                return self.handle_movement(session_id, target_id)

        # --- Character interaction pipeline ---
        state_before = gs.model_dump()

        # 1. Evaluate
        evaluator_output = self._evaluate(player_input, gs, pkg)

        # 2. Apply state update
        gs = self._state_updater.apply_progress(gs, evaluator_output, pkg.logic)

        # 3. Build constraints
        constraints = self._constraint_builder.build_constraints(
            gs, evaluator_output, pkg.logic,
        )

        # 4. Respond
        dialogue = self._respond(player_input, gs, pkg, constraints, evaluator_output)

        # 5. Record turn
        turn_record = TurnRecord(
            player_input=player_input,
            speaker=self._speaker_name(gs, pkg),
            speaker_type="character",
            dialogue=dialogue,
        )
        gs = self._state_updater.append_turn(gs, turn_record)

        # 6. Update summary based on discovered topics
        if gs.conversation_state.discovered_topics:
            topics = ", ".join(gs.conversation_state.discovered_topics)
            gs.conversation_state.summary = (
                f"Topics discussed so far: {topics}."
            )

        # 7. Increment turn index and persist
        session.turn_index += 1
        self._store.update_session(session_id, gs)

        # 8. Write trace
        self._write_trace(
            session_id,
            session.turn_index,
            player_input=player_input,
            evaluator_output=evaluator_output,
            constraints=constraints,
            dialogue=dialogue,
            state_before=state_before,
            state_after=gs.model_dump(),
        )

        return session.turn_index, self._build_character_turn(gs, pkg, dialogue)

    def handle_movement(self, session_id: str, target_location: str) -> tuple[int, TurnResult]:
        """Move the player to a new location. Returns (turn_index, narrator TurnResult)."""
        session = self._store.get_session(session_id)
        gs = session.game_state
        pkg = session.scenario_package

        state_before = gs.model_dump()
        gs = self._state_updater.apply_movement(gs, target_location, pkg.logic)

        # Build narrator dialogue from templates
        dialogue = self._narrator_for_movement(gs, pkg, target_location)

        # Record narrator turn in conversation history
        turn_record = TurnRecord(
            player_input=f"[move to {target_location}]",
            speaker="Narrator",
            speaker_type="narrator",
            dialogue=dialogue,
        )
        gs = self._state_updater.append_turn(gs, turn_record)

        # Increment turn index and persist
        session.turn_index += 1
        self._store.update_session(session_id, gs)

        # Write movement trace
        self._write_movement_trace(
            session_id,
            session.turn_index,
            target_location=target_location,
            dialogue=dialogue,
            state_before=state_before,
            state_after=gs.model_dump(),
        )

        return session.turn_index, self._build_narrator_turn(gs, pkg, dialogue)

    def reset_session(self, session_id: str) -> TurnResult:
        """Reset a session to initial state, preserving the session ID. Returns opening scene."""
        session = self._store.get_session(session_id)
        pkg = session.scenario_package
        init = pkg.initial_state

        # Rebuild fresh GameState from the scenario's initial_state
        from backend.app.domain.game_state import (
            CastState,
            ConversationState,
            FlagsState,
            HeirState,
            StewardState,
        )

        fresh_gs = GameState(
            location=init.starting_location,
            addressed_character=init.starting_addressed_character,
            flags=FlagsState(
                archive_unlocked=init.initial_flags.archive_unlocked,
                game_finished=init.initial_flags.game_finished,
            ),
            story_truth=pkg.story.story_truth,
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

        # Overwrite state and reset turn counter, preserving session ID
        session.game_state = fresh_gs
        session.turn_index = 0
        self._store.update_session(session_id, fresh_gs)

        return self._build_narrator_turn(
            fresh_gs, pkg, self._opening_dialogue(pkg),
        )

    def switch_addressed_character(self, session_id: str, character_id: str) -> GameState:
        """Change which character the player is addressing."""
        session = self._store.get_session(session_id)
        gs = session.game_state

        if character_id not in gs.available_characters:
            raise ValueError(
                f"Character '{character_id}' is not available. "
                f"Available: {gs.available_characters}"
            )

        gs = gs.model_copy(update={"addressed_character": character_id})
        self._store.update_session(session_id, gs)
        return gs

    def get_latest_trace(self, session_id: str) -> dict | None:
        """Return the latest trace for a session, or *None*."""
        if self._trace_logger is None:
            return None
        return self._trace_logger.read_latest_trace(session_id)

    # ------------------------------------------------------------------
    # Evaluate / Respond — delegates to real services or falls back to mock
    # ------------------------------------------------------------------

    def _evaluate(
        self,
        player_input: str,
        gs: GameState,
        pkg: ScenarioPackage,
    ) -> ProgressEvaluatorOutput:
        if self._evaluator is not None:
            return self._evaluator.evaluate(player_input, gs, pkg)
        return self._mock_evaluate(player_input, gs)

    def _respond(
        self,
        player_input: str,
        gs: GameState,
        pkg: ScenarioPackage,
        constraints: ResponseConstraints,
        evaluator_output: ProgressEvaluatorOutput,
    ) -> str:
        if self._responder is not None:
            return self._responder.respond(
                gs, evaluator_output, constraints, player_input, pkg,
            )
        return self._mock_respond(player_input, gs, pkg, constraints)

    # ------------------------------------------------------------------
    # Mock fallbacks (used when LLM services are not injected, e.g. tests)
    # ------------------------------------------------------------------

    @staticmethod
    def _mock_evaluate(player_input: str, game_state: GameState) -> ProgressEvaluatorOutput:
        """Return a no-op evaluator result."""
        return ProgressEvaluatorOutput(
            intent="question",
            target=game_state.addressed_character,
            matched_claim_ids=[],
            matched_gate_condition_ids=[],
            state_effects=StateEffects(),
            explanation="[Mock evaluator — no claims matched]",
        )

    @staticmethod
    def _mock_respond(
        player_input: str,
        game_state: GameState,
        package: ScenarioPackage,
        constraints: ResponseConstraints,
    ) -> str:
        """Return hardcoded character dialogue."""
        char_name = "Unknown"
        for c in package.characters.characters:
            if c.id == game_state.addressed_character:
                char_name = c.name
                break
        return f"[Mock — received: '{player_input}'] {char_name} considers your words carefully."

    # ------------------------------------------------------------------
    # Narrator helpers
    # ------------------------------------------------------------------

    def _narrator_for_movement(
        self, gs: GameState, pkg: ScenarioPackage, target_location: str,
    ) -> str:
        """Build narrator text for a location transition."""
        if gs.flags.game_finished and self._prompt_builder is not None:
            # Archive discovery + ending
            discovery = self._prompt_builder.build_narrator_text(
                "archive_discovery", {},
            )
            ending = self._prompt_builder.build_narrator_text("ending", {})
            return f"{discovery}\n\n{ending}"

        if gs.flags.game_finished:
            return f"You enter the archive. {pkg.story.ending_summary}"

        # Normal scene transition
        loc_name = target_location
        loc_desc = target_location
        for loc in pkg.locations.locations:
            if loc.id == target_location:
                loc_name = loc.name
                loc_desc = loc.description
                break

        if self._prompt_builder is not None:
            return self._prompt_builder.build_narrator_text(
                "scene_transition",
                {"location_name": loc_name, "location_description": loc_desc},
            )
        return f"You move to {loc_desc}"

    @staticmethod
    def _resolve_location(
        target_raw: str, gs: GameState, pkg: ScenarioPackage,
    ) -> str | None:
        """Resolve a user-typed location name to a location ID."""
        # Direct ID match
        if target_raw in {loc.id for loc in pkg.locations.locations}:
            return target_raw
        # Match against location names (case-insensitive)
        for loc in pkg.locations.locations:
            if target_raw == loc.name.lower() or target_raw in loc.name.lower():
                return loc.id
        return None

    # ------------------------------------------------------------------
    # Trace logging
    # ------------------------------------------------------------------

    def _write_trace(
        self,
        session_id: str,
        turn_index: int,
        *,
        player_input: str,
        evaluator_output: ProgressEvaluatorOutput,
        constraints: ResponseConstraints,
        dialogue: str,
        state_before: dict,
        state_after: dict,
    ) -> None:
        if self._trace_logger is None:
            return
        self._trace_logger.write_trace(
            session_id,
            turn_index,
            {
                "turn_index": turn_index,
                "player_input": player_input,
                "evaluator_output": evaluator_output.model_dump(),
                "constraints": constraints.model_dump(),
                "responder_output": dialogue,
                "state_before": state_before,
                "state_after": state_after,
            },
        )

    def _write_movement_trace(
        self,
        session_id: str,
        turn_index: int,
        *,
        target_location: str,
        dialogue: str,
        state_before: dict,
        state_after: dict,
    ) -> None:
        if self._trace_logger is None:
            return
        self._trace_logger.write_trace(
            session_id,
            turn_index,
            {
                "turn_index": turn_index,
                "type": "movement",
                "target_location": target_location,
                "narrator_dialogue": dialogue,
                "state_before": state_before,
                "state_after": state_after,
            },
        )

    # ------------------------------------------------------------------
    # Turn result builders
    # ------------------------------------------------------------------

    def _build_narrator_turn(
        self, gs: GameState, pkg: ScenarioPackage, dialogue: str,
    ) -> TurnResult:
        return TurnResult(
            speaker_type="narrator",
            speaker="Narrator",
            dialogue=dialogue,
            location=gs.location,
            background_url=self._background_url(gs, pkg),
            portrait_url=None,
            available_characters=gs.available_characters,
            available_exits=gs.available_exits,
            suggestions=self._suggestions(gs, pkg),
            game_finished=gs.flags.game_finished,
        )

    def _build_character_turn(
        self, gs: GameState, pkg: ScenarioPackage, dialogue: str,
    ) -> TurnResult:
        return TurnResult(
            speaker_type="character",
            speaker=self._speaker_name(gs, pkg),
            dialogue=dialogue,
            location=gs.location,
            background_url=self._background_url(gs, pkg),
            portrait_url=self._portrait_url(gs, pkg),
            available_characters=gs.available_characters,
            available_exits=gs.available_exits,
            suggestions=self._suggestions(gs, pkg),
            game_finished=gs.flags.game_finished,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _speaker_name(gs: GameState, pkg: ScenarioPackage) -> str:
        for c in pkg.characters.characters:
            if c.id == gs.addressed_character:
                return c.name
        return gs.addressed_character

    def _background_url(self, gs: GameState, pkg: ScenarioPackage) -> str:
        raw = pkg.assets.backgrounds.get(gs.location, "")
        if raw:
            return f"{self._asset_base_url}/{raw}"
        return ""

    def _portrait_url(self, gs: GameState, pkg: ScenarioPackage) -> str | None:
        raw = pkg.assets.portraits.get(gs.addressed_character)
        if raw:
            return f"{self._asset_base_url}/{raw}"
        return raw

    @staticmethod
    def _suggestions(gs: GameState, pkg: ScenarioPackage) -> list[str]:
        sug = pkg.prompt_context.suggestions_by_context
        if gs.flags.game_finished:
            return []
        if gs.flags.archive_unlocked:
            return sug.get("post_unlock", [])
        if gs.conversation_state.steward_pressure > 0:
            return sug.get("mid_game", [])
        return sug.get("start", [])

    @staticmethod
    def _opening_dialogue(pkg: ScenarioPackage) -> str:
        """Build narrator opening text from the scenario."""
        loc = next(
            (l for l in pkg.locations.locations if l.id == pkg.initial_state.starting_location),
            None,
        )
        loc_desc = loc.description if loc else "You find yourself somewhere unknown."
        return f"{pkg.story.premise} {loc_desc}"
