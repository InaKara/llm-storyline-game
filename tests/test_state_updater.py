"""Tests for the state updater — pure state transition logic."""

import pytest

from backend.app.domain.game_state import (
    CastState,
    FlagsState,
    GameState,
    StewardState,
    TurnRecord,
)
from backend.app.domain.progress_models import ProgressEvaluatorOutput, StateEffects
from backend.app.domain.scenario_models import (
    Claim,
    ConstraintRuleSet,
    ConstraintRules,
    EndCondition,
    Gate,
    PressureRules,
    ScenarioLogic,
    StoryTruth,
)
from backend.app.services.state_updater import StateUpdater


@pytest.fixture()
def updater() -> StateUpdater:
    return StateUpdater()


@pytest.fixture()
def logic() -> ScenarioLogic:
    return ScenarioLogic(
        claims=[
            Claim(id="claim_steward_possesses_testament", description="C1"),
            Claim(id="claim_steward_withholding", description="C2"),
            Claim(id="claim_motive_control", description="C3"),
        ],
        gates=[
            Gate(
                id="archive_unlock",
                required_claim_ids=[
                    "claim_steward_possesses_testament",
                    "claim_steward_withholding",
                    "claim_motive_control",
                ],
                effect="unlock_archive",
                description="All three claims unlock the archive",
            )
        ],
        end_conditions=[
            EndCondition(
                trigger="enter_location",
                location="archive",
                requires_flag="archive_unlocked",
                effect="game_finished",
            )
        ],
        pressure_rules=PressureRules(min_claims_for_pressure=1, max_pressure=2),
        constraint_rules=ConstraintRules(
            steward_before_unlock=ConstraintRuleSet(may_yield=False, may_deny=True, may_deflect=True, may_hint=False),
            steward_after_unlock=ConstraintRuleSet(may_yield=True, may_deny=False, may_deflect=False, may_hint=False),
            heir_default=ConstraintRuleSet(may_yield=False, may_deny=False, may_deflect=False, may_hint=True),
        ),
    )


@pytest.fixture()
def initial_gs() -> GameState:
    return GameState(
        location="study",
        addressed_character="steward",
        story_truth=StoryTruth(
            hidden_item="testament",
            current_holder="steward",
            motive="control",
            authority_transfers_to="heir",
        ),
    )


def test_no_matches_no_state_change(updater, initial_gs, logic):
    output = ProgressEvaluatorOutput(intent="question")
    gs = updater.apply_progress(initial_gs, output, logic)
    assert gs.flags.archive_unlocked is False
    assert gs.conversation_state.steward_pressure == 0


def test_partial_claims_increase_pressure(updater, initial_gs, logic):
    output = ProgressEvaluatorOutput(
        intent="accusation",
        state_effects=StateEffects(increase_steward_pressure=True),
    )
    gs = updater.apply_progress(initial_gs, output, logic)
    assert gs.conversation_state.steward_pressure == 1
    assert gs.flags.archive_unlocked is False


def test_pressure_capped_at_max(updater, initial_gs, logic):
    output = ProgressEvaluatorOutput(
        intent="accusation",
        state_effects=StateEffects(increase_steward_pressure=True),
    )
    gs = initial_gs
    for _ in range(5):
        gs = updater.apply_progress(gs, output, logic)
    assert gs.conversation_state.steward_pressure == 2  # max_pressure


def test_full_accusation_unlocks_archive(updater, initial_gs, logic):
    output = ProgressEvaluatorOutput(
        intent="accusation",
        matched_claim_ids=[
            "claim_steward_possesses_testament",
            "claim_steward_withholding",
            "claim_motive_control",
        ],
    )
    gs = updater.apply_progress(initial_gs, output, logic)
    assert gs.flags.archive_unlocked is True
    assert gs.cast_state.steward.yielded is True


def test_movement_to_archive_finishes_game(updater, logic):
    gs = GameState(
        location="study",
        addressed_character="steward",
        flags=FlagsState(archive_unlocked=True),
        story_truth=StoryTruth(
            hidden_item="testament",
            current_holder="steward",
            motive="control",
            authority_transfers_to="heir",
        ),
    )
    gs = updater.apply_movement(gs, "archive", logic)
    assert gs.location == "archive"
    assert gs.flags.game_finished is True


def test_movement_blocked_when_locked(updater, initial_gs, logic):
    with pytest.raises(ValueError, match="Cannot move"):
        updater.apply_movement(initial_gs, "archive", logic)


def test_append_turn_trims_to_max(updater, initial_gs, logic):
    gs = initial_gs
    for i in range(8):
        turn = TurnRecord(
            player_input=f"input {i}",
            speaker="Mr. Hargrove",
            speaker_type="character",
            dialogue=f"response {i}",
        )
        gs = updater.append_turn(gs, turn, max_recent=6)
    assert len(gs.conversation_state.recent_turns) == 6
    assert gs.conversation_state.recent_turns[0].player_input == "input 2"


def test_mark_topic_discovered(updater, initial_gs, logic):
    output = ProgressEvaluatorOutput(
        intent="question",
        state_effects=StateEffects(mark_topic_discovered="testament_existence"),
    )
    gs = updater.apply_progress(initial_gs, output, logic)
    assert "testament_existence" in gs.conversation_state.discovered_topics

    # Applying same topic again should not duplicate
    gs = updater.apply_progress(gs, output, logic)
    assert gs.conversation_state.discovered_topics.count("testament_existence") == 1
