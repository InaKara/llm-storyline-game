"""Tests for prompt building — all deterministic, no LLM calls."""

from pathlib import Path

import pytest

from backend.app.domain.game_state import ConversationState, FlagsState, TurnRecord
from backend.app.domain.progress_models import ProgressEvaluatorInput
from backend.app.domain.response_models import CharacterResponderInput, ResponseConstraints
from backend.app.domain.scenario_models import Claim, PromptContext, StyleHints, StoryTruth
from backend.app.services.prompt_builder import PromptBuilder
from backend.app.services.prompt_loader import PromptLoader


@pytest.fixture()
def builder() -> PromptBuilder:
    loader = PromptLoader()
    return PromptBuilder(
        evaluator_templates=loader.load_evaluator_templates(),
        responder_templates=loader.load_responder_templates(),
        narrator_templates=loader.load_narrator_templates(),
    )


@pytest.fixture()
def eval_input() -> ProgressEvaluatorInput:
    return ProgressEvaluatorInput(
        player_utterance="I think you're hiding the testament!",
        visible_scene="study",
        addressed_character="steward",
        conversation_summary="The player has been asking about estate documents.",
        story_truth=StoryTruth(
            hidden_item="testament",
            current_holder="steward",
            motive="control",
            authority_transfers_to="heir",
        ),
        flags=FlagsState(),
        conversation_state=ConversationState(),
    )


@pytest.fixture()
def claims() -> list[Claim]:
    return [
        Claim(id="claim_steward_possesses_testament", description="The steward has the testament"),
        Claim(id="claim_steward_withholding", description="The steward is withholding information"),
        Claim(id="claim_motive_control", description="The steward's motive is control"),
    ]


def test_evaluator_prompt_contains_claims(builder, eval_input, claims):
    _system, task = builder.build_evaluator_prompt(eval_input, claims)
    assert "claim_steward_possesses_testament" in task
    assert "claim_steward_withholding" in task
    assert "claim_motive_control" in task


def test_evaluator_prompt_contains_player_input(builder, eval_input, claims):
    _system, task = builder.build_evaluator_prompt(eval_input, claims)
    assert "I think you're hiding the testament!" in task


def test_evaluator_prompt_contains_location(builder, eval_input, claims):
    _system, task = builder.build_evaluator_prompt(eval_input, claims)
    assert "study" in task


def test_evaluator_schema_is_valid(builder):
    schema = builder.get_evaluator_schema()
    assert schema["type"] == "object"
    assert "intent" in schema["properties"]
    assert "matched_claim_ids" in schema["properties"]


def test_responder_prompt_selects_steward(builder):
    inp = CharacterResponderInput(
        speaker="Mr. Hargrove",
        player_utterance="What do you know?",
        intent="question",
        response_constraints=ResponseConstraints(may_deny=True),
        state_snapshot={"location": "study", "character_id": "steward", "steward_pressure": 1},
    )
    ctx = PromptContext(
        style_hints=StyleHints(tone="gothic mystery", vocabulary=[], era_feeling="Victorian"),
        story_truth_prompt_form="",
        suggestions_by_context={},
    )
    system, task = builder.build_responder_prompt(inp, ctx)
    assert "Mr. Hargrove" in system  # steward system prompt loaded
    assert "steward" in system.lower()


def test_responder_prompt_selects_heir(builder):
    inp = CharacterResponderInput(
        speaker="Lady Ashworth",
        player_utterance="Do you trust the steward?",
        intent="question",
        response_constraints=ResponseConstraints(may_hint=True),
        state_snapshot={"location": "study", "character_id": "heir", "steward_pressure": 0},
    )
    ctx = PromptContext(
        style_hints=StyleHints(tone="gothic mystery", vocabulary=[], era_feeling="Victorian"),
        story_truth_prompt_form="",
        suggestions_by_context={},
    )
    system, task = builder.build_responder_prompt(inp, ctx)
    assert "Lady Ashworth" in system  # heir system prompt loaded
    assert "heir" in system.lower()


def test_responder_prompt_includes_constraints(builder):
    inp = CharacterResponderInput(
        speaker="Mr. Hargrove",
        player_utterance="Confess!",
        intent="accusation",
        response_constraints=ResponseConstraints(may_deny=True, may_deflect=True),
        state_snapshot={"location": "study", "character_id": "steward", "steward_pressure": 2},
    )
    ctx = PromptContext(
        style_hints=StyleHints(tone="gothic mystery", vocabulary=[], era_feeling="Victorian"),
        story_truth_prompt_form="",
        suggestions_by_context={},
    )
    _system, task = builder.build_responder_prompt(inp, ctx)
    assert "may_deny: true" in task
    assert "may_deflect: true" in task
    assert "may_yield: false" in task


def test_evaluator_prompt_includes_recent_turns(builder, claims):
    inp = ProgressEvaluatorInput(
        player_utterance="Tell me more",
        visible_scene="study",
        addressed_character="steward",
        conversation_summary="",
        story_truth=StoryTruth(
            hidden_item="testament", current_holder="steward",
            motive="control", authority_transfers_to="heir",
        ),
        flags=FlagsState(),
        conversation_state=ConversationState(
            recent_turns=[
                TurnRecord(
                    player_input="Hello",
                    speaker="Mr. Hargrove",
                    speaker_type="character",
                    dialogue="Good day.",
                ),
            ]
        ),
    )
    _system, task = builder.build_evaluator_prompt(inp, claims)
    assert "Mr. Hargrove" in task
    assert "Good day." in task
    assert "Player: Hello" in task  # player side of conversation included


def test_narrator_scene_transition(builder):
    text = builder.build_narrator_text(
        "scene_transition",
        {"location_name": "the archive", "location_description": "A dusty room full of records."},
    )
    assert "the archive" in text
    assert "dusty room" in text
