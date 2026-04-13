"""Integration tests for CharacterResponder — mock the runner, verify full flow."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.app.domain.game_state import ConversationState, GameState, TurnRecord
from backend.app.domain.progress_models import ProgressEvaluatorOutput, StateEffects
from backend.app.domain.response_models import ResponseConstraints
from backend.app.services.character_responder import CharacterResponder
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
                    player_input="Where is the testament?",
                    speaker="Mr. Hargrove",
                    speaker_type="character",
                    dialogue="I'm afraid I don't know what you mean.",
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


@pytest.fixture()
def eval_output():
    return ProgressEvaluatorOutput(
        intent="question",
        target="steward",
        matched_claim_ids=["claim_steward_possesses_testament"],
        state_effects=StateEffects(),
        explanation="Player is asking about the testament.",
    )


def test_respond_calls_runner(builder, game_state, scenario_package, eval_output):
    runner = MagicMock()
    runner.run.return_value = "I assure you, there is no such document."

    responder = CharacterResponder(builder, runner)
    result = responder.respond(
        game_state, eval_output,
        ResponseConstraints(may_deny=True),
        "Where is the testament?",
        scenario_package,
    )

    assert result == "I assure you, there is no such document."
    runner.run.assert_called_once()
    sys_prompt, task_prompt = runner.run.call_args.args
    assert isinstance(sys_prompt, str)
    assert isinstance(task_prompt, str)


def test_respond_includes_player_transcript(builder, game_state, scenario_package, eval_output):
    runner = MagicMock()
    runner.run.return_value = "..."

    responder = CharacterResponder(builder, runner)
    responder.respond(
        game_state, eval_output,
        ResponseConstraints(may_deny=True),
        "Tell me about the will",
        scenario_package,
    )

    sys_prompt, task_prompt = runner.run.call_args.args
    # Recent turns should include both player and character sides
    assert "Player: Where is the testament?" in task_prompt
    assert "Mr. Hargrove" in task_prompt


def test_respond_includes_vocabulary_and_era(builder, game_state, scenario_package, eval_output):
    runner = MagicMock()
    runner.run.return_value = "..."

    responder = CharacterResponder(builder, runner)
    responder.respond(
        game_state, eval_output,
        ResponseConstraints(),
        "Hello",
        scenario_package,
    )

    sys_prompt, _task = runner.run.call_args.args
    assert "VOCABULARY GUIDANCE" in sys_prompt
    assert "ERA FEELING" in sys_prompt


def test_respond_steward_system_prompt_loaded(builder, game_state, scenario_package, eval_output):
    """The steward character should use the steward_system.txt template."""
    runner = MagicMock()
    runner.run.return_value = "..."

    responder = CharacterResponder(builder, runner)
    responder.respond(
        game_state, eval_output,
        ResponseConstraints(),
        "Hello",
        scenario_package,
    )

    sys_prompt, _ = runner.run.call_args.args
    assert "Mr. Hargrove" in sys_prompt or "steward" in sys_prompt.lower()


def test_respond_heir_system_prompt(builder, scenario_package, eval_output):
    """The heir character should use the heir_system.txt template."""
    game_state = GameState(
        location="study",
        addressed_character="heir",
        story_truth=scenario_package.story.story_truth,
    )
    runner = MagicMock()
    runner.run.return_value = "..."

    responder = CharacterResponder(builder, runner)
    responder.respond(
        game_state, eval_output,
        ResponseConstraints(may_hint=True),
        "Do you know anything?",
        scenario_package,
    )

    sys_prompt, _ = runner.run.call_args.args
    assert "Lady Ashworth" in sys_prompt or "heir" in sys_prompt.lower()
