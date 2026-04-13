"""Integration tests for ProgressEvaluator — mock the runner, verify full flow."""

from unittest.mock import MagicMock

from pathlib import Path

import pytest

from backend.app.domain.game_state import ConversationState, FlagsState, GameState, TurnRecord
from backend.app.domain.progress_models import ProgressEvaluatorOutput, StateEffects
from backend.app.domain.scenario_models import StoryTruth
from backend.app.services.progress_evaluator import ProgressEvaluator
from backend.app.services.prompt_builder import PromptBuilder
from backend.app.services.prompt_loader import PromptLoader
from backend.app.services.scenario_loader import ScenarioLoader

SCENARIO_ROOT = Path(__file__).resolve().parent.parent / "scenarios"


@pytest.fixture()
def scenario_package():
    loader = ScenarioLoader(SCENARIO_ROOT)
    return loader.load_scenario_package("manor")


@pytest.fixture()
def game_state(scenario_package):
    return GameState(
        location="study",
        addressed_character="steward",
        story_truth=scenario_package.story.story_truth,
        conversation_state=ConversationState(
            recent_turns=[
                TurnRecord(
                    player_input="Hello there",
                    speaker="Mr. Hargrove",
                    speaker_type="character",
                    dialogue="Good day.",
                ),
            ],
        ),
    )


@pytest.fixture()
def builder():
    loader = PromptLoader()
    return PromptBuilder(
        evaluator_templates=loader.load_evaluator_templates(),
        responder_templates=loader.load_responder_templates(),
        narrator_templates=loader.load_narrator_templates(),
    )


def test_evaluate_calls_runner_with_prompts(builder, game_state, scenario_package):
    expected_output = ProgressEvaluatorOutput(
        intent="accusation",
        target="steward",
        matched_claim_ids=["claim_steward_possesses_testament"],
        state_effects=StateEffects(),
        explanation="Player accused steward of hiding testament.",
    )
    runner = MagicMock()
    runner.run.return_value = expected_output

    evaluator = ProgressEvaluator(builder, runner)
    result = evaluator.evaluate("You're hiding the testament!", game_state, scenario_package)

    assert result is expected_output
    runner.run.assert_called_once()
    _sys, _task, schema = runner.run.call_args.args
    assert isinstance(_sys, str)
    assert isinstance(_task, str)
    assert "You're hiding the testament!" in _task
    assert isinstance(schema, dict)


def test_evaluate_includes_player_input_in_prompt(builder, game_state, scenario_package):
    runner = MagicMock()
    runner.run.return_value = ProgressEvaluatorOutput(intent="other")

    evaluator = ProgressEvaluator(builder, runner)
    evaluator.evaluate("Tell me more", game_state, scenario_package)

    _sys, task, _ = runner.run.call_args.args
    assert "Player: Hello there" in task  # recent turn player side
    assert "Mr. Hargrove" in task  # recent turn character side


def test_evaluate_uses_story_truth_prompt_form(builder, game_state, scenario_package):
    runner = MagicMock()
    runner.run.return_value = ProgressEvaluatorOutput(intent="other")

    evaluator = ProgressEvaluator(builder, runner)
    evaluator.evaluate("Hello", game_state, scenario_package)

    _sys, task, _ = runner.run.call_args.args
    # The prompt_context has story_truth_prompt_form — it should appear in task
    if scenario_package.prompt_context.story_truth_prompt_form:
        assert scenario_package.prompt_context.story_truth_prompt_form in task
