"""Applies evaluator results and movement to GameState."""

from __future__ import annotations

from backend.app.domain.game_state import FlagsState, GameState, TurnRecord
from backend.app.domain.progress_models import ProgressEvaluatorOutput
from backend.app.domain.scenario_models import ScenarioLogic


class StateUpdater:
    """Pure-logic component that produces new GameState from evaluator output."""

    def apply_progress(
        self,
        game_state: GameState,
        evaluator_output: ProgressEvaluatorOutput,
        scenario_logic: ScenarioLogic,
    ) -> GameState:
        """Apply evaluator results to game state. Returns updated state."""
        # Work on copies of mutable nested objects
        flags = game_state.flags.model_copy()
        conv = game_state.conversation_state.model_copy()
        cast = game_state.cast_state.model_copy(deep=True)

        effects = evaluator_output.state_effects

        # Steward pressure
        if effects.increase_steward_pressure:
            conv.steward_pressure = min(
                conv.steward_pressure + 1,
                scenario_logic.pressure_rules.max_pressure,
            )

        # Discovered topics
        if effects.mark_topic_discovered and effects.mark_topic_discovered not in conv.discovered_topics:
            conv.discovered_topics.append(effects.mark_topic_discovered)

        # Gate evaluation — check if matched claims satisfy any gate
        matched = set(evaluator_output.matched_claim_ids)
        for gate in scenario_logic.gates:
            required = set(gate.required_claim_ids)
            if required.issubset(matched):
                if gate.effect == "unlock_archive":
                    flags.archive_unlocked = True
                    cast.steward.yielded = True
                    # Max out pressure when gate fires so behaviour guide
                    # aligns with the yield constraint
                    conv.steward_pressure = (
                        scenario_logic.pressure_rules.max_pressure
                    )

        return game_state.model_copy(
            update={
                "flags": flags,
                "conversation_state": conv,
                "cast_state": cast,
            }
        )

    def apply_movement(
        self,
        game_state: GameState,
        new_location: str,
        scenario_logic: ScenarioLogic,
    ) -> GameState:
        """Move to a new location. Returns updated state.

        Raises ValueError if the move is not allowed.
        """
        if new_location not in game_state.available_exits:
            raise ValueError(
                f"Cannot move to '{new_location}' from '{game_state.location}'. "
                f"Available exits: {game_state.available_exits}"
            )

        flags = game_state.flags.model_copy()

        # Check end conditions
        for ec in scenario_logic.end_conditions:
            if (
                ec.trigger == "enter_location"
                and ec.location == new_location
                and ec.requires_flag
                and getattr(flags, ec.requires_flag, False)
            ):
                if ec.effect == "game_finished":
                    flags.game_finished = True

        return game_state.model_copy(
            update={
                "location": new_location,
                "flags": flags,
            }
        )

    def append_turn(
        self,
        game_state: GameState,
        turn: TurnRecord,
        max_recent: int = 6,
    ) -> GameState:
        """Append a turn to conversation history, trimming to max_recent."""
        conv = game_state.conversation_state.model_copy(deep=True)
        conv.recent_turns.append(turn)
        if len(conv.recent_turns) > max_recent:
            conv.recent_turns = conv.recent_turns[-max_recent:]
        conv.last_speaker = turn.speaker
        return game_state.model_copy(update={"conversation_state": conv})
