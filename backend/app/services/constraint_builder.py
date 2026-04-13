"""Derives response constraints from current game state and scenario logic."""

from __future__ import annotations

from backend.app.domain.game_state import GameState
from backend.app.domain.progress_models import ProgressEvaluatorOutput
from backend.app.domain.response_models import ResponseConstraints
from backend.app.domain.scenario_models import ScenarioLogic


class ConstraintBuilder:
    """Produces ResponseConstraints based on who is addressed and current state."""

    def build_constraints(
        self,
        game_state: GameState,
        evaluator_output: ProgressEvaluatorOutput,
        scenario_logic: ScenarioLogic,
    ) -> ResponseConstraints:
        """Return the constraint set the responder must obey."""
        rules = scenario_logic.constraint_rules

        if game_state.addressed_character == "heir":
            rule_set = rules.heir_default
        elif game_state.flags.archive_unlocked:
            rule_set = rules.steward_after_unlock
        else:
            rule_set = rules.steward_before_unlock

        return ResponseConstraints(
            may_yield=rule_set.may_yield,
            may_deny=rule_set.may_deny,
            may_deflect=rule_set.may_deflect,
            may_hint=rule_set.may_hint,
        )
