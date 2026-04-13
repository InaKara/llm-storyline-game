"""Domain-level evaluation boundary — translates game state to evaluator prompts."""

from __future__ import annotations

from backend.app.ai.evaluator_runner import EvaluatorRunner
from backend.app.domain.game_state import GameState
from backend.app.domain.progress_models import ProgressEvaluatorInput, ProgressEvaluatorOutput
from backend.app.domain.scenario_models import ScenarioPackage
from backend.app.services.prompt_builder import PromptBuilder


class ProgressEvaluator:
    """Prepares evaluator input, calls the runner, returns typed output."""

    def __init__(self, prompt_builder: PromptBuilder, runner: EvaluatorRunner) -> None:
        self._builder = prompt_builder
        self._runner = runner

    def evaluate(
        self,
        player_utterance: str,
        game_state: GameState,
        scenario_package: ScenarioPackage,
    ) -> ProgressEvaluatorOutput:
        """Build context, compose prompt, call LLM, return structured output."""
        evaluator_input = ProgressEvaluatorInput(
            player_utterance=player_utterance,
            visible_scene=game_state.location,
            addressed_character=game_state.addressed_character,
            conversation_summary=game_state.conversation_state.summary,
            story_truth=scenario_package.story.story_truth,
            flags=game_state.flags,
            conversation_state=game_state.conversation_state,
        )

        system_prompt, task_prompt = self._builder.build_evaluator_prompt(
            evaluator_input,
            scenario_package.logic.claims,
            prompt_context=scenario_package.prompt_context,
        )
        schema = self._builder.get_evaluator_schema()

        return self._runner.run(system_prompt, task_prompt, schema)
