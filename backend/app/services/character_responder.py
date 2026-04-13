"""Domain-level response boundary — translates game state to responder prompts."""

from __future__ import annotations

from backend.app.ai.responder_runner import ResponderRunner
from backend.app.domain.game_state import GameState
from backend.app.domain.progress_models import ProgressEvaluatorOutput
from backend.app.domain.response_models import CharacterResponderInput, ResponseConstraints
from backend.app.domain.scenario_models import ScenarioPackage
from backend.app.services.prompt_builder import PromptBuilder


class CharacterResponder:
    """Builds responder input, calls the runner, returns dialogue."""

    def __init__(self, prompt_builder: PromptBuilder, runner: ResponderRunner) -> None:
        self._builder = prompt_builder
        self._runner = runner

    def respond(
        self,
        game_state: GameState,
        evaluator_output: ProgressEvaluatorOutput,
        response_constraints: ResponseConstraints,
        player_utterance: str,
        scenario_package: ScenarioPackage,
    ) -> str:
        """Build context, compose prompt, call LLM, return dialogue string."""
        # Find character definition and name
        speaker = game_state.addressed_character
        character_def = None
        for c in scenario_package.characters.characters:
            if c.id == game_state.addressed_character:
                speaker = c.name
                character_def = c
                break

        responder_input = CharacterResponderInput(
            speaker=speaker,
            player_utterance=player_utterance,
            intent=evaluator_output.intent,
            target=evaluator_output.target,
            matched_claim_ids=evaluator_output.matched_claim_ids,
            state_snapshot={
                "location": game_state.location,
                "character_id": game_state.addressed_character,
                "steward_pressure": game_state.conversation_state.steward_pressure,
                "summary": game_state.conversation_state.summary,
                "recent_turns": [
                    {
                        "player_input": t.player_input,
                        "speaker": t.speaker,
                        "dialogue": t.dialogue,
                    }
                    for t in game_state.conversation_state.recent_turns
                ],
            },
            response_constraints=response_constraints,
        )

        system_prompt, task_prompt = self._builder.build_responder_prompt(
            responder_input,
            scenario_package.prompt_context,
            character_def=character_def,
        )

        return self._runner.run(system_prompt, task_prompt)
