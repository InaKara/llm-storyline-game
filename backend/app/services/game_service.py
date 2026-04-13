"""Thin coordinator that orchestrates the full turn pipeline (mock LLM in Phase 3)."""

from __future__ import annotations

from backend.app.core.session_store import SessionStore
from backend.app.domain.game_state import GameState, TurnRecord
from backend.app.domain.progress_models import ProgressEvaluatorOutput, StateEffects
from backend.app.domain.response_models import ResponseConstraints, TurnResult
from backend.app.domain.scenario_models import ScenarioPackage
from backend.app.services.constraint_builder import ConstraintBuilder
from backend.app.services.session_initializer import SessionInitializer
from backend.app.services.state_updater import StateUpdater


class GameService:
    """Orchestrates session lifecycle and the turn pipeline."""

    def __init__(
        self,
        store: SessionStore,
        initializer: SessionInitializer,
        state_updater: StateUpdater,
        constraint_builder: ConstraintBuilder,
    ) -> None:
        self._store = store
        self._initializer = initializer
        self._state_updater = state_updater
        self._constraint_builder = constraint_builder

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
        """Process one player turn. Returns (turn_index, TurnResult)."""
        session = self._store.get_session(session_id)
        gs = session.game_state
        pkg = session.scenario_package

        # 1. Mock evaluator — no claims matched, intent = question
        evaluator_output = self._mock_evaluate(player_input, gs)

        # 2. Apply state update
        gs = self._state_updater.apply_progress(gs, evaluator_output, pkg.logic)

        # 3. Build constraints
        constraints = self._constraint_builder.build_constraints(
            gs, evaluator_output, pkg.logic,
        )

        # 4. Mock responder — constraints are forwarded (used by real LLM in Phase 4)
        dialogue = self._mock_respond(player_input, gs, pkg, constraints)

        # 5. Record turn
        turn_record = TurnRecord(
            player_input=player_input,
            speaker=self._speaker_name(gs, pkg),
            speaker_type="character",
            dialogue=dialogue,
        )
        gs = self._state_updater.append_turn(gs, turn_record)

        # 6. Increment turn index and persist
        session.turn_index += 1
        self._store.update_session(session_id, gs)

        return session.turn_index, self._build_character_turn(gs, pkg, dialogue)

    def handle_movement(self, session_id: str, target_location: str) -> tuple[int, TurnResult]:
        """Move the player to a new location. Returns (turn_index, narrator TurnResult)."""
        session = self._store.get_session(session_id)
        gs = session.game_state
        pkg = session.scenario_package

        gs = self._state_updater.apply_movement(gs, target_location, pkg.logic)

        # Find location description
        loc_desc = target_location
        for loc in pkg.locations.locations:
            if loc.id == target_location:
                loc_desc = loc.description
                break

        dialogue = f"You move to {loc_desc}"
        if gs.flags.game_finished:
            dialogue = (
                f"You enter the archive. {pkg.story.ending_summary}"
            )

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

    # ------------------------------------------------------------------
    # Mock implementations (replaced by real LLM in Phase 4)
    # ------------------------------------------------------------------

    @staticmethod
    def _mock_evaluate(player_input: str, game_state: GameState) -> ProgressEvaluatorOutput:
        """Return a no-op evaluator result. Replaced by real LLM evaluator in Phase 4."""
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
        constraints: "ResponseConstraints",
    ) -> str:
        """Return hardcoded character dialogue. Replaced by real LLM responder in Phase 4.

        The *constraints* parameter is accepted so the pipeline contract is
        exercised end-to-end even with the mock.  Phase 4 will forward these
        constraints into the real LLM prompt.
        """
        char_name = "Unknown"
        for c in package.characters.characters:
            if c.id == game_state.addressed_character:
                char_name = c.name
                break
        return f"[Mock — received: '{player_input}'] {char_name} considers your words carefully."

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

    @staticmethod
    def _background_url(gs: GameState, pkg: ScenarioPackage) -> str:
        return pkg.assets.backgrounds.get(gs.location, "")

    @staticmethod
    def _portrait_url(gs: GameState, pkg: ScenarioPackage) -> str | None:
        return pkg.assets.portraits.get(gs.addressed_character)

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
